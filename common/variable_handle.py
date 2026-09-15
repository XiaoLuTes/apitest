import json
import re
from typing import Any

import allure
import jsonpath

from common import run_state, yaml_util
from common.logger import logger
from common.yaml_util import YamlVariableError


class VariableNotFoundError(Exception):
    """变量未定义或读取失败

    修复点：原实现取不到变量时只打印一行日志就 break，
    结果是带着未替换的 ${变量} 字面量继续发请求，
    最终表现为"请求串到奇怪路径 / 断言期望值里带 ${} "这类难排查的假失败。
    现在改为立即抛错，用例直接失败并给出明确原因。
    """
    pass


class ExtractValueError(Exception):
    """extract 表达式未提取到内容"""
    pass


class UpstreamDependencyError(Exception):
    """依赖的前置用例失败，变量未产出 / 不可信

    这类情况不算“用例本身写错”，由执行器捕获后把当前用例标记为 skip，
    避免出现“一条根因 + N 条连环红”的报告噪声。
    """
    pass


class VariableHandle:
    # 增加最大递归深度限制，防止变量循环引用导致死循环
    MAX_REPLACE_DEPTH = 10

    @staticmethod
    def replace_value(data: Any, current_depth: int = 0) -> Any:
        """递归替换变量（支持嵌套变量）

        :param data: 原始数据（str/dict/list/数字等）
        :param current_depth: 变量嵌套深度（只有"变量套变量"才累加）
        :return: 替换后的原始类型数据（dict/list/str/int等）
        """
        # 深度保护
        if current_depth > VariableHandle.MAX_REPLACE_DEPTH:
            raise VariableNotFoundError(
                f"变量替换递归深度超过上限({VariableHandle.MAX_REPLACE_DEPTH})，可能存在变量循环引用，请检查变量文件"
            )
        # 空值
        if data is None:
            return None
        # 1. 处理字典类型：递归替换每个value
        if isinstance(data, dict):
            new_dict = {}
            for key, value in data.items():
                new_dict[key] = VariableHandle.replace_value(value, current_depth)
            return new_dict
        # 2. 处理列表类型：递归替换每个元素
        if isinstance(data, list):
            new_list = []
            for item in data:
                new_list.append(VariableHandle.replace_value(item, current_depth))
            return new_list
        # 3. 处理字符串类型：替换${变量}
        if isinstance(data, str):
            str_data = data
            # 循环替换所有${变量}，直到没有匹配项
            while True:
                match = re.search(r'\$\{([^}]+)}', str_data)
                if not match:
                    break
                full_match = match.group(0)  # 例如 ${headers2}
                var_name = match.group(1)    # 例如 headers2
                # 读取变量（取不到立即抛错，不再保留字面量继续执行）
                var_value = VariableHandle._get_variable(var_name)
                # 递归替换变量值内部的嵌套变量
                var_value = VariableHandle.replace_value(var_value, current_depth + 1)
                # 替换：根据变量类型决定是否转字符串
                if isinstance(var_value, (dict, list)):
                    replace_str = json.dumps(var_value, ensure_ascii=False)
                else:
                    replace_str = str(var_value)
                str_data = str_data.replace(full_match, replace_str, 1)
                logger.debug(f"替换变量 {var_name} -> {replace_str[:50]}...")

            # 尝试将字符串还原为字典/列表（针对headers、data这类JSON字符串）
            return VariableHandle._try_load_json(str_data)

        # 4. 其他类型（数字/布尔）：直接返回
        return data

    @staticmethod
    def _get_variable(var_name: str):
        """读取变量值，取不到时立即抛错"""
        try:
            return yaml_util.read_yaml(var_name)
        except YamlVariableError as e:
            # 变量由某条失败 / 跳过的上游用例负责产出时，交给执行器按“跳过”处理
            reason = run_state.untrusted_reason(var_name)
            if reason:
                logger.warning(f"变量 ${{{var_name}}} 不可用：{reason}")
                raise UpstreamDependencyError(f"变量 ${{{var_name}}} 未产出（{reason}）") from e
            logger.error(f"变量替换失败：{e}")
            raise VariableNotFoundError(
                f"变量 ${{{var_name}}} 未定义，用例无法继续执行；"
                f"请检查 variable 目录下的全局变量文件，以及前置用例的 extract 提取结果"
            ) from e
        except Exception as e:
            logger.error(f"读取变量 {var_name} 失败：{e}", exc_info=True)
            raise VariableNotFoundError(f"读取变量 ${{{var_name}}} 失败：{e}") from e

    @staticmethod
    def find_variables(*values) -> set:
        """扫描用例字段里引用的 ${变量名}（用于依赖检查，判断是否依赖了失败的上游用例）"""
        names = set()
        for value in values:
            names |= VariableHandle._scan_variables(value)
        return names

    @staticmethod
    def _scan_variables(value) -> set:
        """递归扫描字符串 / 字典 / 列表里的 ${变量名}"""
        if isinstance(value, str):
            return set(re.findall(r'\$\{([^}]+)}', value))
        if isinstance(value, dict):
            return set().union(*[VariableHandle._scan_variables(v) for v in value.values()]) if value else set()
        if isinstance(value, (list, tuple)):
            return set().union(*[VariableHandle._scan_variables(v) for v in value]) if value else set()
        return set()

    @staticmethod
    def find_extract_keys(extract) -> list:
        """解析 extract 里要产出的变量名（容错：解析失败时退化为正则匹配 key）"""
        if not extract:
            return []
        try:
            parsed = VariableHandle._parse_json_like(extract, name="extract")
            return list(parsed.keys()) if isinstance(parsed, dict) else []
        except Exception:
            return re.findall(r'"([^"]+)"\s*:', str(extract))

    @staticmethod
    def _try_load_json(text: Any) -> Any:
        """字符串看起来是JSON对象/数组时还原为dict/list，否则原样返回

        修复：原先用 startswith/endswith 判断且不做去空格，
        前后带空格或换行的JSON不会被还原，会被当成普通字符串直接发出去。
        """
        if not isinstance(text, str):
            return text
        stripped = text.strip()
        if stripped.startswith(('{', '[')) and stripped.endswith(('}', ']')):
            try:
                return json.loads(stripped)
            except json.JSONDecodeError:
                logger.debug(f"字符串形似JSON但解析失败，按普通字符串处理：{stripped[:100]}")
        return text

    @staticmethod
    def _parse_json_like(text: Any, name: str = "断言") -> dict:
        """把用例里填写的JSON文本解析成字典
        兼容用例中的不规范写法：换行、多余转义双引号、key/value缺引号。
        :param text: Excel单元格内容（JSON文本或已是dict）
        :param name: 出错时的提示名称（断言/extract）
        """
        if isinstance(text, dict):
            return text
        if not isinstance(text, str):
            raise ValueError(f"{name}格式错误，必须是JSON对象文本或字典，实际：{text!r}")

        cleaned = text.strip().replace('\n', '').replace('\r', '')
        if not (cleaned.startswith('{') and cleaned.endswith('}')):
            raise ValueError(f"{name}格式错误，必须以 {{ }} 包裹：{text}")

        # 1. 标准JSON
        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError as e:
            # 2. 兼容双引号被转义成 "" 的写法
            repaired = cleaned.replace('""', '"')
            if repaired != cleaned:
                try:
                    parsed = json.loads(repaired)
                    VariableHandle._check_dict(parsed, name)
                    return parsed
                except json.JSONDecodeError:
                    pass
            # 3. 降级：兼容无引号的 key/value 写法，例如 {key:$.data.token}
            logger.info(f"{name}标准JSON解析失败，尝试降级解析：{cleaned} | 错误：{e}")
            normalized = re.sub(r'([{,])\s*(\w+)\s*:', r'\1"\2":', cleaned)
            normalized = re.sub(r':\s*([^"\s][^,}]*)', r':"\1"', normalized)
            try:
                parsed = json.loads(normalized)
            except json.JSONDecodeError as e2:
                raise ValueError(f"{name}无法解析：{cleaned} | 错误：{e2}") from e2
        return VariableHandle._check_dict(parsed, name)

    @staticmethod
    def _check_dict(parsed: Any, name: str) -> dict:
        """校验解析结果必须是字典"""
        if not isinstance(parsed, dict):
            raise ValueError(f"{name}必须是JSON对象，实际：{type(parsed).__name__}")
        return parsed

    @staticmethod
    @allure.step("提取变量")
    def extract_value(req: Any, extract: Any) -> None:
        """提取变量并写入yaml

        提取表达式判定规则（明确化，不再靠字符串猜测）：
        - 以 $ 开头：按 JSONPath 提取
        - 其余：按正则提取，有捕获组时取第1个捕获组，否则取整个匹配内容
        """
        # 无提取：None、"" 、空dict/空list 都视为不提取
        if not extract:
            return
        try:
            extract_dict = VariableHandle._parse_json_like(extract, name="extract")
        except ValueError as e:
            logger.error(f"extract解析失败：{e}")
            raise ExtractValueError(f"extract格式错误：{e}") from e

        for key, expr in extract_dict.items():
            if not expr:
                continue
            expr = str(expr).strip()
            # JSONPath提取
            if expr.startswith('$'):
                try:
                    resp_json = req.json()
                except ValueError as e:
                    raise ExtractValueError(
                        f"响应不是合法JSON，无法使用JSONPath提取变量[{key}]，响应内容：{req.text[:200]}"
                    ) from e
                result = jsonpath.jsonpath(resp_json, expr)
                if result and len(result) > 0:
                    yaml_util.write_yaml({key: result[0]})
                    logger.info(f"JSONPath提取成功: {key} = {result[0]}")
                else:
                    # 修复：原先只告警不报错，导致后续用例拿着不存在的变量继续跑
                    raise ExtractValueError(f"JSONPath {expr} 未提取到内容，变量[{key}]未写入")
            # 正则提取
            else:
                match = re.search(expr, req.text)
                if match:
                    value = match.group(1) if match.groups() else match.group(0)
                    yaml_util.write_yaml({key: value})
                    logger.info(f"正则提取成功: {key} = {value}")
                else:
                    raise ExtractValueError(f"正则 {expr} 未匹配到内容，变量[{key}]未写入")

    @staticmethod
    def compare_value(actual: Any, expected: Any) -> tuple:
        """断言值比较，返回 (是否通过, 比较方式说明)

        规则：
        1、期望值为空值(null/None)时，实际值必须取不到内容
        2、实际值取不到内容(None)时直接失败，并提示jsonpath未匹配
        3、两边都是布尔值时按布尔比较（兼容 true 与 "true"）
        4、两边都是数字时按数值比较（兼容 200 与 "200"、12.0 与 "12.00"）
        5、其余按字符串比较
        """
        # 1. 期望为空值
        if expected is None or (isinstance(expected, str) and expected.strip().lower() in ('null', 'none')):
            return actual is None, "期望空值，实际必须取不到内容"
        # 2. 实际取不到值
        if actual is None:
            return False, "实际值取不到内容（jsonpath未匹配到或值为null）"
        # 3. 布尔值
        if isinstance(actual, bool) or isinstance(expected, bool) or (
                isinstance(expected, str) and expected.strip().lower() in ('true', 'false')):
            return str(actual).strip().lower() == str(expected).strip().lower(), "按布尔值比较"
        # 4. 数字
        num_actual = VariableHandle._to_number(actual)
        num_expected = VariableHandle._to_number(expected)
        if num_actual is not None and num_expected is not None:
            return num_actual == num_expected, "按数值比较"
        # 5. 字符串
        return str(actual) == str(expected), "按字符串比较"

    @staticmethod
    def _to_number(value: Any):
        """把数字或纯数字字符串转成int/float，无法转换时返回None（bool不算数字）"""
        if value is None or isinstance(value, bool):
            return None
        if isinstance(value, (int, float)):
            return value
        if isinstance(value, str):
            text = value.strip()
            if re.fullmatch(r'[+-]?\d+', text):
                return int(text)
            try:
                return float(text)
            except ValueError:
                return None
        return None

    @staticmethod
    @allure.step("断言验证")
    def assert_validata(req: Any, validata: Any) -> list:
        """断言验证（失败时抛出异常标记用例失败）"""
        # 无断言：None、"" 、空dict/空list 都视为无断言
        if not validata:
            logger.info("无断言内容，跳过断言")
            return []
        try:
            validata_dict = VariableHandle._parse_json_like(validata, name="断言")
        except ValueError as e:
            logger.error(f"断言解析失败：{e}")
            raise AssertionError(f"断言格式错误：{e}") from e

        # 响应体只解析一次，避免每条断言都重复解析
        try:
            resp_json = req.json()
        except ValueError as e:
            error_msg = f"响应不是合法JSON，无法执行断言，响应内容：{req.text[:200]}"
            logger.error(error_msg)
            raise AssertionError(error_msg) from e

        results = []
        failed_details = []  # 收集所有失败的断言详情
        for jsonpath_expr, expected_value in validata_dict.items():
            try:
                actual_values = jsonpath.jsonpath(resp_json, jsonpath_expr)
            except Exception as e:
                error_msg = f"断言表达式[{jsonpath_expr}]非法：{e}"
                logger.error(error_msg)
                raise AssertionError(error_msg) from e
            actual_value = actual_values[0] if (actual_values and len(actual_values) > 0) else None

            check_result, compare_way = VariableHandle.compare_value(actual_value, expected_value)
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
                    f"实际值: {actual_value} (类型: {type(actual_value).__name__}) | "
                    f"比较方式: {compare_way}"
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
