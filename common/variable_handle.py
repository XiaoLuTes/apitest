import json
import re
import allure
import jsonpath
from common import yaml_util
from common.logger import logger


class VariableHandle:
    # 增加最大递归深度限制，防止死循环
    MAX_REPLACE_DEPTH = 10

    @staticmethod
    def replace_value(data, current_depth=0):
        """
        递归替换变量（支持嵌套变量）
        :param data: 原始数据（str/dict/list/数字等）
        :param current_depth: 当前递归深度
        :return: 替换后的原始类型数据（dict/list/str/int等）
        """
        # 递归深度保护
        if current_depth > VariableHandle.MAX_REPLACE_DEPTH:
            logger.warning(f"变量替换递归深度超过上限({VariableHandle.MAX_REPLACE_DEPTH})，可能存在循环引用")
            return data
        # 空值
        if data is None:
            return None
        # 1. 处理字典类型：递归替换每个value
        if isinstance(data, dict):
            new_dict = {}
            for key, value in data.items():
                new_dict[key] = VariableHandle.replace_value(value, current_depth + 1)
            return new_dict
        # 2. 处理列表类型：递归替换每个元素
        if isinstance(data, list):
            new_list = []
            for item in data:
                new_list.append(VariableHandle.replace_value(item, current_depth + 1))
            return new_list
        # 3. 处理字符串类型：替换${变量}
        if isinstance(data, str):
            str_data = data
            # 循环替换所有${变量}，直到没有匹配项
            while re.search(r'\$\{([^}]+)}', str_data):
                # 匹配第一个${变量}
                match = re.search(r'\$\{([^}]+)}', str_data)
                if not match:
                    break
                full_match = match.group(0)  # 例如 ${headers2}
                var_name = match.group(1)    # 例如 headers2
                try:
                    # 从yaml读取变量值
                    var_value = yaml_util.read_yaml(var_name)
                    if var_value is None:
                        logger.info(f"变量 {var_name} 未找到，保留原字符串")
                        break
                    # 递归替换变量值内部的嵌套变量
                    var_value = VariableHandle.replace_value(var_value, current_depth + 1)
                    # 替换：根据变量类型决定是否转字符串
                    if isinstance(var_value, (dict, list)):
                        # 字典/列表转JSON字符串后替换（但最终会在外部还原为字典）
                        replace_str = json.dumps(var_value, ensure_ascii=False)
                    else:
                        replace_str = str(var_value)
                    # 执行替换
                    str_data = str_data.replace(full_match, replace_str, 1)
                    logger.info(f"替换变量 {var_name} -> {replace_str[:50]}...")
                except KeyError as e:
                    logger.error(f"变量 {var_name} 不存在: {e}")
                    break
                except Exception as e:
                    logger.error(f"替换变量 {var_name} 失败: {e}", exc_info=True)
                    break

            # 尝试将字符串还原为字典/列表（针对headers这类JSON字符串）
            try:
                # 仅当字符串是JSON格式时才解析为字典/列表
                if str_data.startswith(('{', '[')) and str_data.endswith(('}', ']')):
                    return json.loads(str_data)
                else:
                    return str_data
            except json.JSONDecodeError:
                # 不是JSON格式，返回原始字符串
                return str_data

        # 4. 其他类型（数字/布尔）：直接返回
        return data

    @staticmethod
    @allure.step(f"提取变量")
    def extract_value(req, extract):
        """提取变量并写入yaml"""
        if extract is None or extract == "":
            return
        try:
            # 解析extract为字典
            extract_dict = {}
            if isinstance(extract, str):
                # 清理格式：关键修复——替换转义双引号、多余空格
                cleaned_extract = extract.strip().replace('\n', '').replace('\r', '')
                # 处理双引号转义问题（"" → "）
                cleaned_extract = cleaned_extract.replace('""', '"')
                # 处理非标准JSON格式（如 {key:$.data.token}）
                if cleaned_extract.startswith('{') and cleaned_extract.endswith('}'):
                    # 兼容无引号的key/value
                    cleaned_extract = re.sub(r'([{,]\s*)(\w+)(\s*:)', r'\1"\2"\3', cleaned_extract)
                    cleaned_extract = re.sub(r':\s*([^"$\s][^,}]+)', r':"\1"', cleaned_extract)

                try:
                    extract_dict = json.loads(cleaned_extract)
                    logger.debug(f"Extract解析成功: {extract_dict}")
                except json.JSONDecodeError as e:
                    logger.info(f"解析extract失败: {cleaned_extract} |错误: {str(e)},尝试降级解析")
                    # 降级手动解析
                    content = cleaned_extract.strip('{}').strip()
                    if ':' in content:
                        key, value = content.split(':', 1)
                        extract_dict = {
                            key.strip().strip('"').strip("'"):
                                value.strip().strip('"').strip("'")
                        }
            else:
                extract_dict = extract
            # 提取变量并写入yaml
            for key, expr in extract_dict.items():
                if not expr:
                    continue
                # 正则提取
                if ".*?" in expr or ".+?" in expr:
                    match = re.search(expr, req.text)
                    if match:
                        yaml_util.write_yaml({key: match.group(0)})
                        logger.info(f"正则提取成功: {key} = {match.group(0)}")
                    else:
                        logger.warning(f"正则 {expr} 未匹配到内容")
                # JSONPath提取
                elif "$." in expr:
                    result = jsonpath.jsonpath(req.json(), expr)
                    if result and len(result) > 0:
                        yaml_util.write_yaml({key: result[0]})
                        logger.info(f"JSONPath提取成功: {key} = {result[0]}")
                    else:
                        logger.warning(f"JSONPath {expr} 未提取到内容")
                else:
                    logger.warning(f"无效的提取表达式: {expr}")
        except Exception as e:
            logger.error(f"提取变量失败: {e}", exc_info=True)

    @staticmethod
    @allure.step(f"断言验证")
    def assert_validata(req, validata):
        """断言验证（失败时抛出异常标记用例失败）"""
        if validata is None or validata == "":
            logger.info("无断言内容，跳过断言")
            return []
        try:
            # 解析断言为字典
            validata_dict = {}
            if isinstance(validata, str):
                cleaned_validata = validata.strip().replace('\n', '').replace('\r', '')
                try:
                    validata_dict = json.loads(cleaned_validata)
                except json.JSONDecodeError:
                    logger.error(f"解析断言失败: {cleaned_validata}")
                    # 手动解析
                    if cleaned_validata.startswith('{') and cleaned_validata.endswith('}'):
                        content = cleaned_validata.strip('{}').strip()
                        if ':' in content:
                            key, value = content.split(':', 1)
                            validata_dict = {key.strip(): value.strip()}
            else:
                validata_dict = validata
            if not isinstance(validata_dict, dict):
                error_msg = f"断言必须是字典类型，实际: {type(validata_dict)}"
                logger.error(error_msg)
                raise AssertionError(error_msg)

            # 执行断言
            results = []
            failed_details = []  # 收集所有失败的断言详情
            for jsonpath_expr, expected_value in validata_dict.items():
                actual_values = jsonpath.jsonpath(req.json(), jsonpath_expr)
                actual_value = actual_values[0] if (actual_values and len(actual_values) > 0) else None
                # 转字符串比较
                check_result = str(actual_value) == str(expected_value)
                results.append({
                    "key": jsonpath_expr,
                    "expected": expected_value,
                    "actual": actual_value,
                    "check_result": check_result
                })
                if check_result:
                    msg = f"断言成功: {jsonpath_expr} = {actual_value}"
                    logger.info(msg)
                    allure.attach(f"断言成功", msg)
                else:
                    fail_msg = (
                        f"断言项[{jsonpath_expr}]失败 | "
                        f"期望值: {expected_value} (类型: {type(expected_value).__name__}) | "
                        f"实际值: {actual_value} (类型: {type(actual_value).__name__})"
                    )
                    logger.error(fail_msg)
                    failed_details.append(fail_msg)
            # 处理断言失败
            if failed_details:
                # 构建汇总失败信息
                fail_summary = (
                        f"\n========== 断言失败汇总 ==========\n"
                        f"总计失败断言数: {len(failed_details)}\n"
                        + "\n".join([f"{i + 1}. {msg}" for i, msg in enumerate(failed_details)])
                        + "\n=================================="
                )
                allure.attach(f"断言失败", fail_summary)
                raise AssertionError(fail_summary)  # 抛出断言失败异常
            logger.info("所有断言验证通过")
            return results
        # 捕获解析/执行过程中的非断言异常（如JSON解析失败、接口响应格式错误等）
        except AssertionError as ae:
            # 预期内的断言失败，直接向上抛出
            raise ae
        except Exception as e:
            # 非预期的异常，打印错误信息
            error_msg = f"断言执行异常: {str(e)}"
            logger.error(error_msg)
            allure.attach(f"断言执行异常", error_msg)
            raise AssertionError(error_msg)  # 转为断言异常抛出
