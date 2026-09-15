import json

import allure
import pytest

from config.setting import setting
from common import request_util, excel_read, run_state
from common.logger import logger
from common.variable_handle import UpstreamDependencyError, VariableHandle
from common.database import DatabaseUtils


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

    def _skip_case(self, file, case_id, reason, extract_keys=None):
        """把用例标记为跳过：写结果文件、计入跳过数、把它要产出的变量标记为不可信"""
        logger.warning(f"用例 {case_id}-{file.get('name')} 跳过: {reason}")
        sheet, row_num = file.get('sheet'), file.get('row_num')
        if sheet is not None and row_num is not None:
            try:
                excel_read.Excel.record_result(self.fileload, sheet, row_num, file.get('result_col', 7),
                                               f"【跳过】{reason}")
            except Exception:
                pass
        run_state.record_outcome("skipped")
        run_state.mark_untrusted(extract_keys, f"用例{case_id}跳过")
        pytest.skip(f"用例 {case_id} 跳过：{reason}")

    def execute(self, file):
        case_id = None
        name = None
        extract_keys = []
        extract_done = False
        self.req = None
        try:
            sheet = file['sheet']
            row_num = file['row_num']  # 用例真实行号，用于回写结果
            result_col = file.get('result_col', 7)  # 结果列，用于回写结果
            case_id = file['case_id']

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

            if method == 'db_select':
                self._db_utils.verify_mysql_data(data, validata)
            elif method == 'db_update':
                sql_result = self._db_utils.execute_mysql_update(data)
                if validata is None or validata == "":
                    logger.info(f"未填写断言，不做判断处理")
                elif not self._db_utils.verify_affected_rows(sql_result, validata):
                    raise AssertionError(f"数据库更新影响行数不符合预期，期望: {validata}, 实际: {sql_result}")
                else:
                    logger.info(f"数据库更新行数校验通过，期望: {validata}, 实际: {sql_result}")
            else:
                url = self.build_url(name, file['url'])
                logger.info(f"\n实际请求url:{url},\n实际请求参数{data}")
                self.req = request_util.send_request(method=method, url=url, data=data, headers=headers)
                allure.attach(body='' + url + '', name='请求路径', attachment_type=allure.attachment_type.TEXT)
                allure.attach(body=json.dumps(headers, ensure_ascii=False, default=str), name='请求头',
                              attachment_type=allure.attachment_type.JSON)
                allure.attach(body=json.dumps(data, ensure_ascii=False, default=str), name='请求参数',
                              attachment_type=allure.attachment_type.JSON)
                allure.attach(body=self.req.text, name='响应参数', attachment_type=allure.attachment_type.JSON)
                excel_read.Excel.record_result(self.fileload, sheet, row_num, result_col, self.req.text)
                if extract:
                    VariableHandle.extract_value(self.req, extract)
                extract_done = True
                self.validate_result = VariableHandle.assert_validata(self.req, validata)

            if self.req is not None:
                logger.info(f"返回结果：{self.req.text},\n断言结果:{self.validate_result}")
            logger.info(f"测试通过")
            run_state.mark_trusted(extract_keys)
            run_state.record_outcome("passed")

        except UpstreamDependencyError as e:
            # 2、替换变量时才发现依赖失败（例如 ${headers_x} 内部引用了失败用例产出的 token）→ 同样按跳过处理
            self._skip_case(file, case_id, str(e), extract_keys)

        except Exception as e:
            case_id_str = str(case_id) if case_id is not None else "未知用例ID"
            name_str = str(name) if name is not None else str(file.get('name') or "未知用例名称")
            # 3、本条用例要产出的变量标记为不可信，让依赖它的后续用例跳过而不是连环报错
            if setting.INVALIDATE_ON_ANY_FAILURE or not extract_done:
                run_state.mark_untrusted(extract_keys, f"用例{case_id_str}执行失败")
            run_state.record_outcome("failed")
            # 请求还没发出去就失败时，把失败原因写进结果文件，便于直接看结果表排查
            if self.req is None:
                try:
                    excel_read.Excel.record_result(self.fileload, file.get('sheet'), file.get('row_num'),
                                                   file.get('result_col', 7), f"【失败】{str(e)}")
                except Exception:
                    pass
            logger.error(f"用例 {case_id_str}-{name_str} 执行失败: {str(e)}")
            raise
