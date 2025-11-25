import json
import allure
from config.setting import setting
from common import request_util, excel_read
from common.logger import logger
from common.variable_handle import VariableHandle


class Executor:
    def __init__(self):
        self.api = None
        self.req = None
        self.validate_result = None
        self._db_utils = None
        self.test_url = setting.TEST_URL
        self.fileload = setting.TEST_FLIELOAD

    def _ensure_database_connection(self):
        """确保数据库连接建立"""
        if self._db_utils is None:
            from common.database import DatabaseUtils
            logger.info("创建数据库连接")
            self._db_utils = DatabaseUtils()
            self._db_utils.connect()

    def _close_database_connection(self):
        """关闭数据库连接"""
        if self._db_utils:
            try:
                self._db_utils.close()
            except Exception as e:
                logger.warning(f"关闭数据库连接时发生错误: {e}")
            finally:
                self._db_utils = None

    def execute(self, file):
        try:
            case_id = file['case_id']
            name = file['name']
            allure.dynamic.title(name)
            method = file['method']
            url = self.test_url + file['url']
            data = VariableHandle.replace_value(file['data'])
            headers = VariableHandle.replace_value(file['headers'])
            extract = file['extract']
            validate = file['validata']
            if method == 'db_select':
                self._ensure_database_connection()
                self._db_utils.execute_query(data, validate)
            elif method == 'db_update':
                self._ensure_database_connection()
                self._db_utils.execute_update(data, validate)
            else:
                self.req = request_util.send_request(method=method, url=url, data=data, headers=headers)
                allure.attach(body='' + url + '', name='请求路径', attachment_type=allure.attachment_type.TEXT)
                allure.attach(body=json.dumps(headers), name='请求头', attachment_type=allure.attachment_type.JSON)
                allure.attach(body=json.dumps(data), name='请求参数', attachment_type=allure.attachment_type.JSON)
                allure.attach(body=self.req.text, name='响应参数', attachment_type=allure.attachment_type.JSON)
                if extract:
                    VariableHandle.extract_value(self.req, extract)
                excel_read.Excel().excel_write(self.fileload, file['case_id'] + 1, 7, self.req.text)  # 写入接口返回
                self.validate_result = VariableHandle.assert_validata(self.req, validate)
            logger.info(
                f"用例id：{case_id}用例名称：{name},请求方式：{method},请求url：{url},请求参数：{data},返回结果：{self.req.text},断言结果:"
                f"{self.validate_result}")
        finally:
            self._close_database_connection()
