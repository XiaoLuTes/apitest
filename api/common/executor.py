import json
from typing import Any

import allure
import pytest
from api.config.setting import setting
from api.common import request_util, excel_read, run_state, file_util, yaml_util, retry, payroll_util
from api.common.logger import logger
from api.common.variable_handle import ExtractValueError, UpstreamDependencyError, VariableHandle, VariableNotFoundError
from api.common.database import DatabaseUtils


class Executor:
    def __init__(self):
        self.api = None
        self.req = None
        self.validate_result = None
        self._db_utils = DatabaseUtils()
        self.test_url = setting.TEST_URL
        self.fileload = setting.TEST_FLIELOAD
        self.default_url = setting.DEFAULT_URL

    def build_url(self, name, path):
        """根据用例名称前缀选择端，并拼接用例中的接口路径
        修复点：原实现中「用例名称未匹配到端」时只取了 base_url，把用例里的 url 路径丢掉了，
        会请求到站点根路径；这里统一改为「环境地址 + 用例路径」。
        另外支持用例直接写全量 URL（http/https 开头），此时不再拼接环境地址。
        """
        path = VariableHandle.replace_value(path)
        path = '' if path is None else str(path)
        if path.startswith(('http://', 'https://')):
            return path

        base_url = None
        for url_key, url_value in self.test_url.items():
            if name.startswith(url_key):
                base_url = url_value
                break
        if base_url is None:
            base_url = self.test_url[self.default_url]
            logger.warning(f"用例名称未以{list(self.test_url.keys())}开头，按默认端[{self.default_url}]拼接请求地址")
        return base_url + path

    def _record_verdict(self, file, text):
        """把用例结果（通过 / 失败：原因 / 跳过：原因）写进结果文件的 result 列"""
        sheet, row_num = file.get('sheet'), file.get('row_num')
        if sheet is None or row_num is None:
            return
        try:
            excel_read.Excel.record_result(self.fileload, sheet, row_num, file.get('result_col'), text)
        except Exception:
            pass

    def _skip_case(self, file, case_id, reason, extract_keys=None):
        """把用例标记为跳过：写结果文件、计入跳过数、把它要产出的变量标记为不可信"""
        logger.warning(f"用例 {case_id}-{file.get('name')} 跳过: {reason}")
        self._record_verdict(file, f"跳过：{reason}")
        run_state.record_outcome("skipped", sheet=file.get('sheet'))  # 按sheet页统计跳过
        run_state.mark_untrusted(extract_keys, f"用例{case_id}跳过")
        pytest.skip(f"用例 {case_id} 跳过：{reason}")

    def execute(self, file):
        case_id = None
        name = None
        extract_keys = []
        extract_done = False
        self.req = None
        error = None
        try:
            sheet = file['sheet']
            row_num = file['row_num']  # 用例真实行号，用于回写结果
            case_id = file['case_id']
            allure.dynamic.title(str(file.get('name') or case_id))
            # 1、依赖检查：本条用例引用的变量若来自失败 / 跳过的上游用例，直接跳过，避免“一条根因 + N 条连环红”
            extract_keys = VariableHandle.find_extract_keys(file.get('extract'))
            blocked = {
                v: run_state.untrusted_reason(v)
                for v in VariableHandle.find_variables(file.get('name'), file.get('url'), file.get('data'),
                                                       file.get('headers'), file.get('validata'))
                if run_state.is_untrusted(v)
            }
            if blocked:
                self._skip_case(
                    file, case_id,
                    "依赖的前置用例失败 -> " + "；".join(f"${{{v}}}：{reason}" for v, reason in blocked.items()),
                    extract_keys,
                )
            # 先记录用例标识（用 Excel 里的原始名称）：即使后面替换变量失败，日志里也能查到是哪条用例
            logger.info("\n----------------------------")
            logger.info(f"执行用例:{case_id}-{file.get('name')}")
            name = VariableHandle.replace_value(file['name'])
            name = name if isinstance(name, str) else str(name)
            allure.dynamic.title(name)
            method = file['method']
            method = str(method).strip().lower() if method is not None else ''
            if not method:
                raise ValueError(f"用例 {case_id} 未填写method，无法执行")

            data = VariableHandle.replace_value(file['data'])
            headers = VariableHandle.replace_value(file['headers'])
            extract = file.get('extract')
            validata = VariableHandle.replace_value(file['validata'])

            if method in ('db_select', 'db_update') and not data:
                raise ValueError(f"用例 {case_id} 未填写SQL，无法执行数据库操作")

            # payrollconfirm：payroll薪资包业务的特殊处理
            if method == 'payrollconfirm':
                method, confirm_url, data = payroll_util.build_confirm_request(data, case_id=case_id)
                if confirm_url and not str(file.get('url') or '').strip():
                    file['url'] = confirm_url

            # editexcel：用 WPS / Excel 引擎填写单元格并重算（仅支持本机，Jenkins本机运行session0不支持）
            if method == 'editexcel':
                if not isinstance(data, dict):
                    raise ValueError(f"用例 {case_id} 的 editexcel data 必须是 JSON 对象（file / cells / sheet）")
                edit_file = str(data.get('file') or '').strip()
                edit_cells = data.get('cells')
                index_cells = data.get('index_cells')
                if not edit_file:
                    raise ValueError(f"用例 {case_id} 的 editexcel 缺少 file（待编辑的 xlsx 路径）")
                if index_cells:
                    # 按指标编号填数：同样是payroll国家模板的特殊处理
                    edit_cells = payroll_util.resolve_cells_by_indicator(edit_file, index_cells, case_id=case_id)
                if not isinstance(edit_cells, dict) or not edit_cells:
                    raise ValueError(f"用例 {case_id} 的 editexcel 缺少 cells，格式：{{\"单元格\": 值}}")
                file_util.edit_excel_by_wps(edit_file, edit_cells, data.get('sheet'))
            elif method == 'db_select':
                self._db_utils.verify_mysql_data(data, validata)
            elif method == 'db_update':
                sql_result = self._db_utils.execute_mysql_update(data)
                if validata is None or validata == "":
                    logger.info(f"未填写断言，不做判断处理")
                elif not self._db_utils.verify_affected_rows(sql_result, validata):
                    raise AssertionError(f"数据库更新影响行数不符合预期，期望: {validata}, 实际: {sql_result}")
                else:
                    logger.info(f"数据库更新行数校验通过，期望: {validata}, 实际: {sql_result}")
            elif method == 'download':
                url = self.build_url(name, file['url'])
                download_dir = None
                download_var = None
                download_params = data
                if isinstance(data, dict):
                    download_dir = data.get('dir')
                    download_var = data.get('var')
                    download_params = data.get('params')
                if validata:
                    logger.warning(f"用例 {case_id}：download 不支持 validata 断言，已忽略")
                logger.info(f"\n实际请求url:{url},\n实际请求参数{download_params}")
                resp = request_util.send_request(method='download', url=url, data=download_params, headers=headers)
                try:
                    saved = file_util.save_response_file(resp, case_id=case_id, target_dir=download_dir)
                finally:
                    resp.close()
                if download_var:
                    # 统一写正斜杠：Windows 反斜杠会让后续 upload / editexcel 的 {"file": "${变量}"} JSON 解析失败
                    yaml_util.write_yaml({download_var: saved.replace('\\', '/')})
                excel_read.Excel.record_result(self.fileload, sheet, row_num,
                                               file.get('response_col'), f"文件已保存：{saved}")
            else:
                url = self.build_url(name, file['url'])
                attempts, interval = retry.resolve(file.get('retry'))
                logger.info(f"\n实际请求url:{url},\n实际请求参数{data}")

                allure.attach(body='' + url + '', name='请求路径', attachment_type=allure.attachment_type.TEXT)
                allure.attach(body=json.dumps(headers, ensure_ascii=False, default=str), name='请求头',
                              attachment_type=allure.attachment_type.JSON)
                allure.attach(body=json.dumps(data, ensure_ascii=False, default=str), name='请求参数',
                              attachment_type=allure.attachment_type.JSON)

                attempt_no = 0
                last_req: Any = None
                last_req_attempt = 0

                def _attempt():
                    nonlocal extract_done, attempt_no, last_req, last_req_attempt
                    attempt_no += 1
                    self.req = None
                    req = request_util.send_request(method=method, url=url, data=data, headers=headers)
                    self.req = req
                    last_req, last_req_attempt = req, attempt_no
                    excel_read.Excel.record_result(self.fileload, sheet, row_num,
                                                   file.get('response_col'), req.text)
                    if extract:
                        VariableHandle.extract_value(req, extract)
                    extract_done = True
                    self.validate_result = VariableHandle.assert_validata(req, validata, attach=False)

                try:
                    retry.call(_attempt, times=attempts, interval=interval,
                               retry_on=(AssertionError, ExtractValueError), desc=f"用例 {case_id}")
                    passed_details = [f"断言成功: {item['key']} = {item['actual']}"
                                      for item in (self.validate_result or []) if item.get('check_result')]
                    if passed_details:
                        allure.attach(body=VariableHandle.summary_text(passed_details, "成功"),
                                      name='断言成功', attachment_type=allure.attachment_type.TEXT)
                except AssertionError as error:
                    allure.attach(body=str(error), name='断言失败',
                                  attachment_type=allure.attachment_type.TEXT)
                    raise
                finally:
                    if last_req is not None:
                        if last_req_attempt == attempt_no:
                            attach_name = '响应参数（最后一次）' if attempt_no > 1 else '响应参数'
                        else:
                            attach_name = f'响应参数（第 {last_req_attempt} 次尝试，之后未拿到响应）'
                        allure.attach(body=last_req.text, name=attach_name,
                                      attachment_type=allure.attachment_type.JSON)

            if self.req is not None:
                logger.info(f"返回结果：{self.req.text},\n断言结果:{self.validate_result}")
            logger.info(f"测试通过")
            self._record_verdict(file, "通过")
            run_state.mark_trusted(extract_keys)
            run_state.record_outcome("passed", sheet=file.get('sheet'))  # 按sheet页统计成功数

        except UpstreamDependencyError as e:
            # 2、替换变量时才发现依赖失败（例如 ${headers_x} 内部引用了失败用例产出的 token）→ 同样按跳过处理
            self._skip_case(file, case_id, str(e), extract_keys)

        except Exception as e:
            error = e
            case_id_str = str(case_id) if case_id is not None else "未知用例ID"
            name_str = str(name) if name is not None else str(file.get('name') or "未知用例名称")
            # 3、本条用例要产出的变量标记为不可信，让依赖它的后续用例跳过而不是连环报错
            if setting.INVALIDATE_ON_ANY_FAILURE or not extract_done:
                run_state.mark_untrusted(extract_keys, f"用例{case_id_str}执行失败")
            # 失败时带上 sheet 名，按表统计
            run_state.record_outcome("failed", case_id_str, name_str, sheet=file.get('sheet'))
            # 把失败原因写进结果文件的 result 列（接口返回写在 response 列）
            one_line = " ".join(str(e).split())[:500]
            self._record_verdict(file, f"失败：{one_line}")
            logger.error(f"用例 {case_id_str}-{name_str} 执行失败: {str(e)}")

        if error is not None:
            # 用例级失败（断言失败 / 变量未配置 / 提取失败）不打回溯：失败原因在报错信息里已经写清楚了
            if isinstance(error, (AssertionError, ExtractValueError, VariableNotFoundError)):
                pytest.fail(str(error), pytrace=False)
            raise error
