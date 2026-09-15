import numbers

import allure
import pymysql
from pymysql import cursors
from common.logger import logger
from typing import List, Dict, Any
from config.setting import setting


class DatabaseUtils:
    _instance = None

    def __new__(cls):  # 创建一个单例对象，保证executor执行器和conftest调用的是同一个对象
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, '_initialized'):
            return
        self.db_timeout = setting.DB_TIMEOUT
        self.host = str(setting.DB_HOST)
        self.user = str(setting.DB_USER)
        self.password = str(setting.DB_PASSWORD)
        self.database = str(setting.DB_NAME)
        self.port = int(setting.DB_PORT)
        self.timeout = setting.DB_TIMEOUT
        self.connection = None
        self._initialized = True

    def connect(self):
        """建立数据库连接"""
        # 配置缺失时给出明确提示（数据库密码等敏感配置放在项目根目录的 .env 里，不入库）
        missing = [name for name, value in (("DB_HOST", self.host), ("DB_USER", self.user),
                                           ("DB_PASSWORD", self.password), ("DB_NAME", self.database)) if not value]
        if missing:
            raise RuntimeError(f"数据库配置缺失：{','.join(missing)}；请在项目根目录的 .env（或系统环境变量）中配置后重试")

        if self.connection is not None:
            try:
                # 检测连接是否存活，失效则自动重连
                self.connection.ping(reconnect=True)
                logger.info("复用已有数据库连接（连接有效）")
                return self.connection
            except pymysql.MySQLError as e:
                logger.warning(f"现有数据库连接失效（{e}），将重新创建连接")
                self.connection = None

        try:
            self.connection = pymysql.connect(
                host=self.host,
                user=self.user,
                password=self.password,
                database=self.database,
                port=self.port,
                charset='utf8mb4',
                cursorclass=pymysql.cursors.DictCursor,
                connect_timeout=self.timeout
            )
            logger.info("数据库连接成功")
            return self.connection
        except Exception as e:
            logger.error(f"数据库连接失败: {e}")
            # MySQL8的 caching_sha2_password / sha256_password认证需要 cryptography包：
            #服务端缓存过密码时走 fast auth不需要它，一旦服务器重启或改密码导致缓存失效就会报错
            if "cryptography" in str(e):
                logger.error("缺少依赖 cryptography：请在当前 Python环境执行 pip install cryptography（或 pip install -r requirements.txt）")
            #保留原始异常与堆栈（原来 raise Exception会把真正的错误信息丢掉）
            raise

    def close_database_connection(self):
        """关闭数据库连接"""
        if self.connection:
            try:
                self.connection.close()
                logger.info("数据库连接已关闭")
            except Exception as e:
                logger.warning(f"关闭数据库连接时发生错误: {e}")
            finally:
                self.connection = None

    def execute_query(self, sql: str, params=None) -> List[Dict[str, Any]]:
        """执行查询语句"""
        try:
            self.connect()
            with self.connection.cursor() as cursor:
                cursor.execute(sql, params or ())
                result = cursor.fetchall()  # 获取查询结果
                logger.info(f"SQL执行成功")
                return result
        except Exception as e:
            logger.error(f"查询执行失败: {e}, SQL: {sql}")
            raise

    def execute_update(self, sql: str, params=None) -> int:
        """执行更新语句"""
        try:
            self.connect()
            with self.connection.cursor() as cursor:
                cursor.execute(sql, params or ())
                self.connection.commit()  # 提交事务
                rowcount = cursor.rowcount  # 获取影响行数
                return rowcount
        except Exception as e:
            if self.connection:
                self.connection.rollback()
            logger.error(f"更新语句执行失败: {e}, SQL: {sql}")
            raise

    @allure.step("执行数据库验证")
    def verify_mysql_data(self, sql: Any, expected: Any):
        """执行SQL查询并验证结果"""
        try:
            # 记录开始执行的日志
            logger.info(f"执行SQL验证: {sql}")
            logger.info(f"期望结果: {expected}")
            result = self.execute_query(sql)
            allure.attach(str(result), "SQL执行结果", allure.attachment_type.TEXT)
            verification_passed = self.parse_and_verify_expected(result, expected)
            if verification_passed:
                logger.info("数据库验证成功")
            else:
                error_msg = f"数据库验证失败: SQL={sql}, 期望={expected}, 实际结果={result}"
                raise AssertionError(error_msg)

        except TimeoutError as e:
            error_msg = f"数据库验证超时: {str(e)}"
            logger.error(error_msg)
            raise
        except Exception as e:
            # 处理其他所有异常
            error_msg = f"数据库验证执行失败: {str(e)}"
            logger.error(error_msg)
            raise

    def parse_and_verify_expected(self, result, expected) -> bool:
        """解析期望结果并进行验证

        支持的写法：
        - 空 / empty / [] / null / none：查询结果必须为空
        - count:n ：结果行数等于 n；count>:n ：结果行数大于 n
        - contains:xxx ：结果中任一行任一字段包含 xxx
        - 字段=值[,字段2=值2] ：存在某一行各字段都等于期望值
        - 其他：结果只有一行一列时与该值比较，否则只校验结果非空

        修复：原先直接对 expected 调用 .lower()/startswith()，
        当断言列填的是数字（openpyxl 读出来是 int）时会抛 AttributeError，
        这里统一先转成字符串再判断。
        """
        # 统一转字符串，兼容断言列填数字的情况
        exp = "" if expected is None else str(expected).strip()

        # 期望为空：校验查询结果为空
        if exp == "" or exp.lower() in ["empty", "[]", "null", "none"]:
            return len(result) == 0

        # count>:n 结果行数大于n（必须先于count:判断）
        if exp.startswith("count>:"):
            return len(result) > self._to_int(exp.split(":", 1)[1], expected)

        # count:n 结果行数等于n
        if exp.startswith("count:"):
            return len(result) == self._to_int(exp.split(":", 1)[1], expected)

        # contains:xxx 结果中包含xxx
        if exp.startswith("contains:"):
            return self.verify_contains(result, exp.split(":", 1)[1].strip())

        # 字段值验证 - 格式: "字段=值" 或 "字段1=值1,字段2=值2"
        if "=" in exp:
            return self.verify_field_values(result, exp)

        # 直接值比较（用于单值查询）- 当结果只有一行一列时
        if len(result) == 1 and len(result[0]) == 1:
            actual_value = list(result[0].values())[0]
            return self.value_equal(actual_value, exp)

        # 都不匹配时，检查结果是否非空
        return len(result) > 0

    @staticmethod
    def _to_int(value, origin) -> int:
        """把断言里的数字文本转成int，格式不对时给出明确报错"""
        try:
            return int(str(value).strip())
        except ValueError as e:
            raise ValueError(f"数据库断言格式错误，count 后必须是整数，实际：{origin}") from e

    @staticmethod
    def value_equal(actual, expected) -> bool:
        """数据库断言的值比较：至少一方是数字时按数值比较，其余按字符串比较

        修复：原先统一 str() 比较，导致数据库返回 Decimal('12.00') 这类值与断言里的 12 判不相等。
        """
        actual_is_num = isinstance(actual, numbers.Number) and not isinstance(actual, bool)
        expected_is_num = isinstance(expected, numbers.Number) and not isinstance(expected, bool)
        if actual_is_num and expected_is_num:
            return actual == expected
        if actual_is_num or expected_is_num:
            try:
                return float(actual) == float(expected)
            except (TypeError, ValueError):
                return False
        return str(actual) == str(expected)

    @staticmethod
    def verify_contains(result, expected_value: str) -> bool:
        """
        验证结果中包含特定值
        """
        for row in result:
            # 遍历每一行中的每个值
            for value in row.values():
                # 检查期望值是否出现在当前值的字符串形式中
                if expected_value in str(value):
                    return True
        return False

    @staticmethod
    def verify_field_values(result, expected: str) -> bool:
        """
        验证字段值
        Args:
            result: 数据库查询结果
            expected (str): 期望的字段值对
        Returns:
            bool: 是否有行匹配所有期望的字段值
        """
        # 解析期望的字段值对
        expected_pairs = {}  # 创建空字典存储字段值对
        for pair in expected.split(","):  # 按逗号分割多个字段值对
            if "=" in pair:
                key, value = pair.split("=", 1)  # 按等号分割字段名和值
                expected_pairs[key.strip()] = value.strip()
        if not expected_pairs:
            return False
        # 检查是否有行匹配所有期望的字段值
        for row in result:
            match = True  # 假设当前行匹配
            for field, expected_value in expected_pairs.items():
                if field not in row or not DatabaseUtils.value_equal(row[field], expected_value):
                    match = False
                    break
            if match:
                return True
        return False

    @allure.step("执行数据库更新操作")
    def execute_mysql_update(self, sql: Any):
        """
        执行数据库更新操作（INSERT, UPDATE, DELETE）
        Returns:
            int: 影响的行数
        """
        try:
            logger.info(f"执行数据库更新: {sql}")
            affected_rows = self.execute_update(sql)
            logger.info(f"数据库更新成功，影响行数: {affected_rows}")
            return affected_rows  # 返回影响的行数
        except TimeoutError as e:
            error_msg = f"数据库更新超时: {str(e)}"
            logger.error(error_msg)
            raise
        except Exception as e:
            error_msg = f"数据库更新执行失败: {str(e)}"
            logger.error(error_msg)
            raise  # 重新抛出异常

    @staticmethod
    def verify_affected_rows(affected: int, expected: Any) -> bool:
        """校验数据库更新（INSERT/UPDATE/DELETE）的影响行数
        - 空值：不做校验，直接返回 True
        - count:n ：影响行数必须等于 n
        - count>:n：影响行数必须大于 n
        - empty/null/none：影响行数必须为 0
        - 其他值：与影响行数字符串比较
        """
        if expected is None or str(expected).strip() == "":
            return True
        exp = str(expected).strip()
        if exp.startswith("count>:"):
            return affected > int(exp.split(":", 1)[1].strip())
        if exp.startswith("count:"):
            return affected == int(exp.split(":", 1)[1].strip())
        if exp.lower() in ("empty", "null", "none"):
            return affected == 0
        return str(affected) == exp
