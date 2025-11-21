import json
import re
import allure
import jsonpath
import pytest
from common import request_util
from common import yaml_util
from logger import logger
from common import excel_read

fileload = r"D:\python\2022-12\2023-1\test_cloud\test_cloud_saas.xlsx"
# 测试用例绝对路径
class TestFile:
    req = None
    validata_result = {
        'message': '断言'
    }

    def replace_value(self, data):
        # 判断传入data当前的数据类型
        if isinstance(data, dict) or isinstance(data, list):
            # 传入data需要先转换为str类型才能判断$标识符以及取点
            str_data = json.dumps(data, ensure_ascii=False)
        else:
            str_data = str(data)
        if '$' in data:
            # 判断$提取标识符是否在data里面
            for a in range(1, str_data.count("$") + 1):
                # for in range默认从0开始计数，所以此处前面起始值为1，左开右合，所以右边需要+1
                length = len(str_data)
                # 定义str_data的长度
                start_index = str_data.index('${')
                end_index = str_data.index('}', start_index, length + 1)
                # 使用index函数定义起始标识"${"和结束标识"}"的位置
                # 结束标识"}"的定位以起始标识位置开始，到总长度+1的位置结束（由于左开右合所以需要length+1）
                replace_data = str_data[start_index + 2:end_index]
                # 需要替换的值为str_data中start_index起始标识与end_index结束标识中间的字符
                # 因为起始标识"${"占用了两个字符，所以replace_data要从起始标识右边两个字符处开始
                # 此处定义replace_data主要为了去extract.yaml里面查询
                dataa = yaml_util.read_yaml(replace_data)
                if isinstance(dataa, dict) or isinstance(dataa, int):
                    # 判断提取出的变量是否为dict类型，如果是,需要先转化为str类型才能replace替换原有值
                    datab = json.dumps(dataa)
                    str_data = str_data.replace(str_data[start_index:end_index + 1], datab)
                else:
                    # 判断变量是否是int类型，如果是，需要转化为str类型才能replace替换原有值
                    # 如果提取出的变量不是dict类型，需要先替换原有值
                    str_data = str_data.replace(str_data[start_index:end_index + 1], dataa)
            data4 = eval(str_data)
            return data4
            # 替换完成后用eval函数返回dict格式
        elif isinstance(data, str):
            # 如果data不包含$标识符，判断是否为str类型，如果是str，转化为dict返回
            data2 = json.loads(data)
            return data2
        else:
            return data

    def extract_value(self, file):
        file_keys = file.keys()
        # 提取传入file所有的key值
        if "extract" in file_keys:
            if isinstance(file['extract'], str):
                extract = json.loads(file['extract'])
            else:
                extract = file['extract']
                # 判断传入extract数据的数据格式
            if extract is not None:
                # 判断extract传入是否为空（为空则直接跳过）
                for key, value in extract.items():
                    if ".*?" in value or ".+?" in value:
                        yaml_util.write_yaml({key: re.search(self.req.text, key)})
                        # 正则提取
                    elif "$." in value:
                        revalue = jsonpath.jsonpath(self.req.json(), value)
                        yaml_util.write_yaml({key: revalue[0]})
                    # json提取
                    else:
                        print("没有正则表达式或json提取表达式")
            else:
                pass
        else:
            pass

    def assert_validata(self, file):
        """提取断言"""
        file_keys = file.keys()
        if 'validata' in file_keys and file['validata'] is not None:
            # 判断是否存在断言validata关键字且断言条件不为空
            if isinstance(file['validata'], str):
                validata = json.loads(file['validata'])
            else:
                validata = file['validata']
                # 判断传入validata的格式，转换为json格式
            result = []
            for check_key, check_value in validata.items():
                # 提取断言的参数和值
                key = '$.' + check_key + ''
                www = jsonpath.jsonpath(self.req.json(), key)
                # 参数使用jsonpath提取
                value = [str(check_value)]
                # 提取返回中参数对应的值
                if value == www:
                    result.append(True)
                else:
                    result.append(False)
                    # 判断断言是否与接口返回一致
            if False in result:
                error_message = '断言类型[json_value]-->实际结果：%s ；期望结果：%s 不相符，断言失败' \
                                % (self.req.text, file['validata'])
                logger.warning(error_message)
                self.validata_result['message'] = error_message
                pytest.fail(error_message, False)
                # 标记用例fail,继续执行其他用例
                return self.validata_result
            else:
                pass_message = '断言相符，断言通过'
                logger.info(pass_message)
                self.validata_result['message'] = pass_message
                return self.validata_result
        else:
            self.validata_result['message'] = '未发现断言条件'

    # yaml文件用例执行
    # @pytest.mark.parametrize('file', yaml_util.read_yl_yaml("test_cloud/test_yl.yaml", 'cloud'))
    # def test_cloud(self, file):
    #     name = file['name']
    #     url = file['url']
    #     allure.attach(body='' + url + '', name='请求路径', attachment_type=allure.attachment_type.TEXT)
    #     method = file['method']
    #     headers = self.replace_value(file['headers'])
    #     allure.attach(body=json.dumps(headers), name='请求头', attachment_type=allure.attachment_type.JSON)
    #     data = self.replace_value(file['data'])
    #     allure.attach(body=json.dumps(data), name='请求参数', attachment_type=allure.attachment_type.JSON)
    #     self.req = request_util.send_request(method=method, url=url, data=data, headers=headers)
    #     allure.attach(body=self.req.text, name='响应参数', attachment_type=allure.attachment_type.JSON)
    #     self.extract_value(file)
    #     self.assert_validata(file)
    #     logger.logger.info(
    #         f"用例名称：{name},请求方式：{method},请求url：{url},请求参数：{data},服务器返回结果：{self.req.text},断言结果:"
    #         f"{self.validata_result}")
    #     print(self.req.json())
    #     allure.dynamic.title(name)

    # excel用例执行
    @pytest.mark.parametrize('file', excel_read.Excel().excel_read(fileload))
    def test_excel_cloud(self, file):
        # 随便加个注释
        name = file['name']
        allure.dynamic.title(name)
        url = yaml_util.read_yaml('url_saas_real') + file['url']
        allure.attach(body='' + url + '', name='请求路径', attachment_type=allure.attachment_type.TEXT)
        method = file['method']
        headers = self.replace_value(file['headers'])
        allure.attach(body=json.dumps(headers), name='请求头', attachment_type=allure.attachment_type.JSON)
        data = self.replace_value(file['data'])
        allure.attach(body=json.dumps(data), name='请求参数', attachment_type=allure.attachment_type.JSON)
        self.req = request_util.send_request(method=method, url=url, data=data, headers=headers)
        allure.attach(body=self.req.text, name='响应参数', attachment_type=allure.attachment_type.JSON)
        self.extract_value(file)
        excel_read.Excel().excel_write(fileload, file['case_id']+1, 7,
                                       self.req.text)
        self.assert_validata(file)
        logger.info(
            f"用例名称：{name},请求方式：{method},请求url：{url},请求参数：{data},返回结果：{self.req.text},断言结果:"
            f"{self.validata_result}")
        print(self.req.json())
