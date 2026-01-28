import json
import allure
from config.setting import setting
from common import request_util, excel_read
from common.logger import logger
from common.variable_handle import VariableHandle
from common.database import DatabaseUtils


class Executor:
    def __init__(self):
        self.api = None
        self.req = None
        self.validate_result = None
        self._db_utils = DatabaseUtils()
        self.test_url = setting.TEST_URL
        self.fileload = setting.TEST_FLIELOAD
        self.default_url = '管理端'

    def execute(self, file):
        case_id = None
        name = None
        try:
            case_id = file['case_id']
            name = VariableHandle.replace_value(file['name'])
            logger.info("\n----------------------------")
            logger.info(f"执行用例:{case_id}-{str(name)}")
            allure.dynamic.title(name)
            method = file['method']
            for url_key, url_value in self.test_url.items():
                if name.startswith(url_key):
                    url = url_value + VariableHandle.replace_value(file['url'])
                    break
            else:
                url = self.test_url[self.default_url]
            data = VariableHandle.replace_value(file['data'])
            headers = VariableHandle.replace_value(file['headers'])
            extract = file['extract']
            validata = VariableHandle.replace_value(file['validata'])
            if method == 'db_select':
                self._db_utils.verify_mysql_data(data, validata)
            elif method == 'db_update':
                sql_result = self._db_utils.execute_mysql_update(data)
                if validata is None:
                    logger.info(f"未填写断言，不做判断处理")
                elif validata and str(sql_result) != validata:
                    raise AssertionError(f"数据库更新影响行数不匹配，期望: {validata}, 实际: {sql_result}")
            else:
                logger.info(f"\n实际请求url:{url},\n实际请求参数{data}")
                self.req = request_util.send_request(method=method, url=url, data=data, headers=headers)
                allure.attach(body='' + url + '', name='请求路径', attachment_type=allure.attachment_type.TEXT)
                allure.attach(body=json.dumps(headers), name='请求头', attachment_type=allure.attachment_type.JSON)
                allure.attach(body=json.dumps(data), name='请求参数', attachment_type=allure.attachment_type.JSON)
                allure.attach(body=self.req.text, name='响应参数', attachment_type=allure.attachment_type.JSON)
                if extract:
                    VariableHandle.extract_value(self.req, extract)
                excel_read.Excel().excel_write(self.fileload, file['case_id'] + 1, 7, self.req.text)  # 写入接口返回
                self.validate_result = VariableHandle.assert_validata(self.req, validata)
            if self.req is not None:
                logger.info(f"返回结果：{self.req.text},\n断言结果:{self.validate_result}")
            logger.info(f"测试通过")

        except Exception as e:
            case_id_str = str(case_id) if case_id is not None else "未知用例ID"
            name_str = str(name) if name is not None else "未知用例名称"
            logger.error(f"用例 {case_id_str}-{name_str} 执行失败: {str(e)}", exc_info=True)
            raise
