import json
import re
import jsonpath
import pytest
from common import yaml_util
from common.logger import logger


class VariableHandle:

    @staticmethod
    def replace_value(data):
        """替换变量"""
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
                start_index = str_data.index('${')
                end_index = str_data.index('}', start_index, length + 1)
                replace_data = str_data[start_index + 2:end_index]
                # 需要替换的值为str_data中start_index起始标识与end_index结束标识中间的字符
                # 因为起始标识"${"占用了两个字符，所以replace_data要从起始标识右边两个字符处开始
                data_extract = yaml_util.read_yaml(replace_data)
                if isinstance(data_extract, dict) or isinstance(data_extract, int):
                    # 判断提取出的变量是否为dict类型，如果是,需要先转化为str类型才能replace替换原有值
                    data_extract_str = json.dumps(data_extract)
                    str_data = str_data.replace(str_data[start_index:end_index + 1], data_extract_str)
                else:
                    # 判断变量是否是int类型，如果是，需要转化为str类型才能replace替换原有值
                    # 如果提取出的变量不是dict类型，需要先替换原有值
                    str_data = str_data.replace(str_data[start_index:end_index + 1], data_extract)
            data_dict = eval(str_data)
            return data_dict
            # 替换完成后用eval函数返回dict格式
        elif isinstance(data, str):
            # 如果data不包含$标识符，判断是否为str类型，如果是str，转化为dict返回
            data_dict = json.loads(data)
            return data_dict
        else:
            return data

    @staticmethod
    def extract_value(req, file):
        """提取传入file所有的key值"""
        file_keys = file.keys()
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
                        yaml_util.write_yaml({key: re.search(req.text, key)})
                        # 正则提取
                    elif "$." in value:
                        revalue = jsonpath.jsonpath(req.json(), value)
                        yaml_util.write_yaml({key: revalue[0]})
                    # json提取
                    else:
                        print("没有正则表达式或json提取表达式")
            else:
                pass
        else:
            pass

    @staticmethod
    def assert_validata(req, file):
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
                www = jsonpath.jsonpath(req.json(), key)
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
                                % (req.text, file['validata'])
                logger.warning(error_message)
                pytest.fail(error_message, False)
                # 标记用例fail,继续执行其他用例
                return error_message
            else:
                pass_message = '断言相符，断言通过'
                logger.info(pass_message)
                return pass_message
        else:
            message = '未发现断言条件'
            return message
