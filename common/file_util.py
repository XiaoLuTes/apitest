"""文件工具：下载落盘 + 用 WPS / Excel 引擎编辑单元格"""
import os
import re
import time
from pathlib import Path
from urllib.parse import unquote

from config.setting import setting
from common.logger import logger

_EXT_BY_TYPE = {
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
    "application/vnd.ms-excel": ".xls",
    "application/pdf": ".pdf",
    "application/zip": ".zip",
    "text/csv": ".csv",
    "application/json": ".json",
    "text/plain": ".txt",
}

# ---------------------------------------------------------------------------
# 下载
# ---------------------------------------------------------------------------


def filename_from_headers(headers):
    """从响应头推导文件名：优先 Content-Disposition，取不到返回 None"""
    disposition = headers.get("Content-Disposition") or headers.get("content-disposition") or ""
    if not disposition:
        return None
    # RFC 5987：filename*=UTF-8''%E4%B8%AD%E6%96%87.xlsx
    m = re.search(r"filename\*\s*=\s*([^;]+)", disposition, re.I)
    if m:
        value = m.group(1).strip().strip('"')
        if "''" in value:
            value = value.split("''", 1)[1]
        return unquote(value)
    # 普通：filename="abc.xlsx"
    m = re.search(r'filename\s*=\s*"?([^";]+)"?', disposition, re.I)
    return m.group(1).strip() if m else None


def _guess_ext(headers):
    ctype = (headers.get("Content-Type") or "").split(";")[0].strip().lower()
    return _EXT_BY_TYPE.get(ctype, "")


def _unique_path(directory, filename):
    """同名文件已存在时加序号，避免覆盖"""
    target = os.path.join(directory, filename)
    if not os.path.exists(target):
        return target
    stem, ext = os.path.splitext(filename)
    index = 1
    while os.path.exists(os.path.join(directory, f"{stem}_{index}{ext}")):
        index += 1
    return os.path.join(directory, f"{stem}_{index}{ext}")


def save_response_file(response, case_id=None, target_dir=None):
    """把流式响应写入磁盘，返回保存路径

    :param response: requests 的 Response（需以 stream=True 发起）
    :param case_id: 兜底文件名用（服务端没给文件名时）
    :param target_dir: 保存目录，默认 setting.DOWNLOAD_PATH
    :return: 保存后的文件路径
    """
    if not response.ok:
        body = (response.text or "")[:200]
        raise RuntimeError(f"下载失败：HTTP {response.status_code}，响应：{body}")

    directory = target_dir or setting.DOWNLOAD_PATH
    if not os.path.isabs(directory):
        directory = os.path.join(setting.BASE_DIR, directory)   # 相对项目根解析，不依赖运行目录
    os.makedirs(directory, exist_ok=True)

    filename = filename_from_headers(response.headers)
    if not filename:
        filename = f"{case_id or 'download'}_{time.strftime('%Y%m%d_%H%M%S')}{_guess_ext(response.headers)}"
    filename = os.path.basename(str(filename).replace("\\", "/"))   # 防服务端返回带目录的名字
    target = _unique_path(directory, filename)

    written = 0
    with open(target, "wb") as f:
        for chunk in response.iter_content(chunk_size=64 * 1024):
            if chunk:
                f.write(chunk)
                written += len(chunk)

    if written == 0:
        os.remove(target)
        raise RuntimeError(f"下载失败：文件内容为空（HTTP {response.status_code}）")

    logger.info(f"文件已保存：{target}（{written} 字节）")
    return target


# ---------------------------------------------------------------------------
# 编辑
# ---------------------------------------------------------------------------


def edit_excel_by_wps(file_path, cells, sheet_name=None):
    """用 WPS / Excel 引擎填写单元格并重算保存（保留公式、缓存值、图片、样式）

    与 openpyxl 的区别：openpyxl 保存时不会写公式的缓存值，
    值读取型后端（openpyxl / pandas / POI 不 evaluate）会读到 None；
    本方法交给真实表格引擎重算后再保存，缓存值是正确结果。

    :param file_path: 待编辑的 xlsx（原地覆盖；相对路径以项目根目录 setting.BASE_DIR 为基准）
    :param cells: {"单元格": 值}，只应包含输入格，不要写公式格
    :param sheet_name: 可选，重命名第一个 sheet
    :return: 保存后的文件路径
    """
    if not os.path.isabs(file_path):
        file_path = os.path.join(setting.BASE_DIR, file_path)
    if not Path(file_path).exists():
        raise FileNotFoundError(f"文件不存在: {file_path}")

    try:
        import pywintypes
        import win32com.client
    except ImportError as e:
        raise Exception("缺少 pywin32，无法调用 WPS/Excel 引擎（pip install pywin32）") from e

    abs_path = str(Path(file_path).resolve())
    errors = []
    for prog_id in ("KET.Application", "Excel.Application"):   # KET = WPS 表格
        app = None
        workbook = None
        try:
            app = win32com.client.DispatchEx(prog_id)   # 独立进程，不干扰已打开的 WPS
            app.Visible = False
            app.DisplayAlerts = False
            workbook = app.Workbooks.Open(abs_path)
            if workbook.ReadOnly:
                raise RuntimeError(f"文件被占用（只读打开），无法保存: {abs_path}")
            worksheet = workbook.Worksheets(1)
            if sheet_name:
                worksheet.Name = sheet_name
            for cell, value in cells.items():
                cell_range = worksheet.Range(cell)
                if isinstance(value, str):
                    cell_range.NumberFormat = "@"   # 防 00123 / 2026-11-13 被自动转成数字或日期
                cell_range.Value = value
            try:
                app.CalculateFullRebuild()      # 全量重算，结果写入缓存值
            except Exception:
                app.Calculate()                 # WPS 部分版本没有 CalculateFullRebuild
            workbook.Save()
            logger.info(f"Excel已填写并重算({prog_id}): {abs_path} 共修改{len(cells)}个cell")
            return abs_path
        except Exception as e:
            # 用宽捕获：WPS 缺方法时抛的是 AttributeError，不是 com_error，否则走不到 Excel 兜底
            errors.append(f"{prog_id}: {e}")
            logger.warning(f"{prog_id} 编辑失败: {e}")
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
