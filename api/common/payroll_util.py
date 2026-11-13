"""薪资包算薪结果：把填好的国家模板转换成 confirmImport 需要的两个 map

前端在「批量导入算薪结果」里会自己解析国家模板，拼出：
  - excelDistrictDataMap: {结算包编码: "[{id, item{指标编号:{v,t,f,fc}}}]"}（值是 JSON 字符串）
  - countDataMap:         {结算包编码: [{settlementCode, 汇率, 雇主总成本, 发票总额 ...}]}
接口只吃这两个 map，不认本地文件，所以 Excel 驱动的用例必须自己把表读出来。

国家模板结构（所有国家一致）：
  第 5 行 = 指标编号（Index Field ID）
  第 9 行起 = 员工数据行，B 列(指标 XX0) 是结算单编码
  第 7 行 = 币种、第 8 行 = 本月汇总（SUM 公式）
公式格必须读「重算后的值」，因此这里用 WPS/Excel 引擎打开并 CalculateFullRebuild，
而不是 openpyxl（openpyxl 读不到公式的缓存值，只有文件被表格软件保存过才有）。
"""
import json
import os
from pathlib import Path

from api.config.setting import setting
from api.common.logger import logger

# 以下均为payroll业务特殊处理的，所以没放到setting
INDICATOR_ROW = 5          # 指标编号所在行（1-based）
DATA_START_ROW = 9         # 第一个员工数据行
SETTLEMENT_CODE_INDEX = "XX0"
# 非薪资项的说明行/合计行，不参与 item map
SKIP_INDICATOR_PREFIX = ("指标", "规则", "币种", "本月")

# countDataMap 用到的指标编号 -> 接口字段名（与前端解析保持一致）
# 前面的元组是该字段的候选指标编号：不同国家模板的服务费编号不一样
#   （加拿大/香港模板 = 61~64，法国模板 = S1~S4），按顺序取第一个存在的
COUNT_FIELDS = [
    (("SE1",), "settlementCurrencyAndPayrollCurrency"),
    (("SE2",), "invoicingCurrencyAndSettlementCurrency"),
    (("G1",), "totalEmployerCostSc"),
    (("61", "S1"), "serviceFee"),
    (("62", "S2"), "settingUpFee"),
    (("63", "S3"), "otherServiceFee"),
    (("64", "S4"), "chargeAdjustmentFromPastMonths"),
    (("H",), "totalServiceFeeSc"),
    (("I",), "currentPayableSc"),
    (("K",), "vatIc"),
    (("J",), "currentPayableInvoiceAmount"),
    (("L2",), "adjustmentFromPreviousMonthIc"),
    (("M",), "totalInvoiceAmount"),
]


def _abs_path(file_path):
    """相对路径按项目根解析，与 download / editexcel 保持一致"""
    path = str(file_path or "").strip()
    if not path:
        raise ValueError("未指定文件路径")
    if not os.path.isabs(path):
        path = os.path.join(setting.BASE_DIR, path)
    if not Path(path).exists():
        raise FileNotFoundError(f"文件不存在: {path}")
    return str(Path(path).resolve())


def resolve_cells_by_indicator(file_path, index_cells, case_id=None):
    """把 {指标编号: 值} 换算成 {单元格: 值}

    这样 editexcel 不用写死列坐标，换国家模板也不用改用例。
    只读不写，交给 openpyxl 打开即可（不保存，不会丢公式缓存值）。
    """
    import openpyxl

    if not isinstance(index_cells, dict) or not index_cells:
        raise ValueError(f"用例 {case_id} 的 index_cells 必须是对象，格式：{{\"1\": 4500, \"SE1\": 1.15}}")

    path = _abs_path(file_path)
    workbook = openpyxl.load_workbook(path, data_only=True)
    sheet = workbook[workbook.sheetnames[0]]
    col_of_indicator = {}
    for col in range(1, sheet.max_column + 1):
        value = sheet.cell(row=INDICATOR_ROW, column=col).value
        if value is not None and str(value).strip():
            col_of_indicator.setdefault(str(value).strip(), col)
    workbook.close()

    cells = {}
    missing = []
    for indicator, value in (index_cells or {}).items():
        key = str(indicator).strip()
        col = col_of_indicator.get(key)
        if not col:
            missing.append(key)
            continue
        letter = openpyxl.utils.get_column_letter(col)
        cells[f"{letter}{DATA_START_ROW}"] = value
    if missing:
        raise ValueError(f"国家模板中找不到指标编号：{missing}（第{INDICATOR_ROW}行未配置这些指标）")
    logger.info(f"按指标编号换算单元格: {cells}")
    return cells


def _read_grid(path):
    """用 WPS / Excel 打开 → 全量重算 → 读出整个 used range 的值"""
    try:
        import win32com.client
    except ImportError as e:
        raise Exception("缺少 pywin32，无法读取国家模板（pip install pywin32）") from e

    errors = []
    for prog_id in ("KET.Application", "Excel.Application"):   # KET = WPS 表格
        app = None
        workbook = None
        try:
            app = win32com.client.DispatchEx(prog_id)
            app.Visible = False
            app.DisplayAlerts = False
            workbook = app.Workbooks.Open(path)
            try:
                app.CalculateFullRebuild()
            except Exception:
                app.Calculate()
            sheet = workbook.Worksheets(1)
            used = sheet.UsedRange
            grid = used.Value or ()
            first_row = int(used.Row)
            col_count = int(used.Columns.Count)
            logger.info(f"国家模板已读取({prog_id}): {path} 起始行={first_row} 列数={col_count}")
            return grid, first_row, col_count
        except Exception as e:
            # WPS 缺方法时抛 AttributeError，用宽捕获才能走到 Excel 兜底
            errors.append(f"{prog_id}: {e}")
            logger.warning(f"{prog_id} 读取失败: {e}")
        finally:
            if workbook is not None:
                try:
                    workbook.Close(False)
                except Exception:
                    pass
            if app is not None:
                try:
                    app.Quit()
                except Exception:
                    pass
    raise Exception("WPS / Excel 均不可用或调用失败: " + " | ".join(errors))


def _normalize(value):
    """单元格值 -> (值, 类型)；空值统一成空串 + 字符串类型"""
    if value is None:
        return "", "s"
    if isinstance(value, bool):
        return str(value), "s"
    if isinstance(value, (int, float)):
        return value, "n"
    text = str(value)
    return (text, "s") if text != "" else ("", "s")


def read_payroll_rows(file_path):
    """读出国家模板里的每个员工结算行

    :return: (结算包编码或 None, [{id: 结算单编码, item: {指标: {v, t}}}])
    """
    path = _abs_path(file_path)
    grid, first_row, col_count = _read_grid(path)
    last_row = first_row + len(grid) - 1

    def cell(row_no, col_no):
        return grid[row_no - first_row][col_no - 1]

    indicator_of_col = {}
    for col in range(1, col_count + 1):
        value = cell(INDICATOR_ROW, col)
        if value is not None and str(value).strip():
            indicator_of_col[col] = str(value).strip()

    rows = []
    for row_no in range(DATA_START_ROW, last_row + 1):
        item = {}
        settlement_code = None
        for col, indicator in indicator_of_col.items():
            if indicator.startswith(SKIP_INDICATOR_PREFIX):
                continue
            value, value_type = _normalize(cell(row_no, col))
            item[indicator] = {"v": value, "t": value_type}
            if indicator == SETTLEMENT_CODE_INDEX:
                settlement_code = str(value).strip()
        if settlement_code:
            rows.append({"id": settlement_code, "item": item})

    package_code = None
    name = os.path.basename(path)
    if "_" in name:
        package_code = name.split("_", 1)[0]
    logger.info(f"国家模板解析完成：结算包={package_code} 员工行数={len(rows)}")
    return package_code, rows


def build_confirm_body(data):
    """把用例 data 补全成 confirmImport 的请求体

    用例里只需要写：
      {"payrollSalaryPackageId": "${pkg_id}", "file": "${tpl_file}", "url": "${filled_url}"}
    结算包编码默认取国家模板文件名前缀（服务端下载的文件名就是「结算包编码_国家模板.xlsx」），
    也可以用 settlementPackageCode 显式指定。
    """
    if not isinstance(data, dict):
        raise ValueError("payrollconfirm 的 data 必须是 JSON 对象（payrollSalaryPackageId / file / url）")

    payroll_salary_package_id = data.get("payrollSalaryPackageId")
    file_path = data.get("file")
    if not payroll_salary_package_id:
        raise ValueError("payrollconfirm 缺少 payrollSalaryPackageId（薪资包ID）")
    if not file_path:
        raise ValueError("payrollconfirm 缺少 file（已填好的国家模板本地路径）")

    package_code, rows = read_payroll_rows(file_path)
    package_code = str(data.get("settlementPackageCode") or package_code or "").strip()
    if not package_code:
        raise ValueError("payrollconfirm 无法确定结算包编码：请传 settlementPackageCode，或让文件名以结算包编码开头")
    if not rows:
        raise ValueError(f"国家模板里没有解析到员工结算行（第 {DATA_START_ROW} 行起、指标 {SETTLEMENT_CODE_INDEX} 为空）")

    count_list = []
    for row in rows:
        item = row["item"]
        entry = {"settlementCode": row["id"]}
        for indicators, field in COUNT_FIELDS:
            value = None
            for indicator in indicators:   # 多国模板兼容：取第一个存在且非空的指标
                cell = item.get(indicator) or {}
                if cell.get("v") not in (None, ""):
                    value = cell["v"]
                    break
            entry[field] = value
        count_list.append(entry)

    result_urls = data.get("payrollResultFilesUrls") or ([data["url"]] if data.get("url") else [])
    if not result_urls:
        raise ValueError("payrollconfirm 缺少 url（第 5 步校验接口返回的国家模板地址）")

    return {
        "payrollSalaryPackageId": payroll_salary_package_id,
        "payrollResultFilesUrls": result_urls,
        "excelDistrictDataMap": {package_code: json.dumps(rows, ensure_ascii=False)},
        "countDataMap": {package_code: count_list},
        "payrollPayslipMatchList": data.get("payrollPayslipMatchList") or [],
        "bankFilesUrls": data.get("bankFilesUrls") or [],
        "otherFilesUrls": data.get("otherFilesUrls") or [],
    }

CONFIRM_URL = "/api/payrollCalculation/payrollCollect/confirmImport"


def build_confirm_request(payload, case_id=None):
    """payrollconfirm 动作的唯一入口：校验入参 + 组装请求体 + 指定地址

    执行器只负责调用本方法并把返回值套回请求链路，不再关心 payroll 的任何细节。

    :param payload: 用例 data（已做过变量替换）
    :param case_id: 仅用于报错提示
    :return: (method, url, body)
    """
    if not isinstance(payload, dict):
        raise ValueError(f"用例 {case_id} 的 payrollconfirm data 必须是 JSON 对象"
                         f"（payrollSalaryPackageId / file / url）")
    return "post", CONFIRM_URL, build_confirm_body(payload)
