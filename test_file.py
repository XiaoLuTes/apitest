import json
import allure
import pytest
from common import request_util
from common.logger import logger
from common import excel_read
from config.setting import setting
from common.variable_handle import VariableHandle


fileload = setting.TEST_FLIELOAD
# 测试用例文件路径
test_url = setting.TEST_URL
# 测试环境路径
class TestFile:
    # excel用例执行
    @pytest.mark.parametrize('file', excel_read.Excel().excel_read(fileload))
    def test_excel_cloud(self, file):
        name = file['name']
        allure.dynamic.title(name)
        url = test_url + file['url']
        allure.attach(body='' + url + '', name='请求路径', attachment_type=allure.attachment_type.TEXT)
        method = file['method']
        headers = VariableHandle.replace_value(file['headers'])
        data = VariableHandle.replace_value(file['data'])
        self.req = request_util.send_request(method=method, url=url, data=data, headers=headers)
        allure.attach(body=json.dumps(headers), name='请求头', attachment_type=allure.attachment_type.JSON)
        allure.attach(body=json.dumps(data), name='请求参数', attachment_type=allure.attachment_type.JSON)
        allure.attach(body=self.req.text, name='响应参数', attachment_type=allure.attachment_type.JSON)
        if "extract" in file:
            VariableHandle.extract_value(self.req, file)
        excel_read.Excel().excel_write(fileload, file['case_id'] + 1, 7,
                                       self.req.text)
        self.validate_result = VariableHandle.assert_validata(self.req, file)
        logger.info(
            f"用例名称：{name},请求方式：{method},请求url：{url},请求参数：{data},返回结果：{self.req.text},断言结果:"
            f"{self.validate_result}")
        logger.info(f"{self.req.json()}")
