import pymysql
from pymysql import cursors
from common.logger import logger
from typing import List, Dict, Any
from config.setting import setting


class DatabaseUtils:
    def __init__(self):
        self.host = str(setting.DB_HOST)
        self.user = str(setting.DB_USER)
        self.password = str(setting.DB_PASSWORD)
        self.database = str(setting.DB_NAME)
        self.port = int(setting.DB_PORT)
        self.timeout = setting.DB_TIMEOUT
        self.connection = None

    def connect(self):
        """建立数据库连接"""
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
            raise Exception

    def execute_query(self, query: str, params=None) -> List[Dict[str, Any]]:
        """
        执行查询语句
        args:
            query(str): 要执行的sql语句
            param: sql语句的参数，默认为空
        return:
            List[Dict[str, Any]]: 查询结果列表，每个结果都是一个字典
        """
        try:
            if self.connection is None:
                self.connect()

            with self.connection.cursor() as cursor:
                cursor.execute(query, params or ())
                result = cursor.fetchall()  # 获取查询结果
                logger.info(f"SQL执行成功")
                return result
        except Exception as e:
            logger.error(f"查询执行失败: {e}, SQL: {query}")
            raise

    def execute_update(self, query: str, params=None) -> int:
        """执行更新语句"""
        try:
            if self.connection is None:
                self.connect()

            with self.connection.cursor() as cursor:
                cursor.execute(query, params or ())
                self.connection.commit()  # 提交事务
                rowcount = cursor.rowcount  # 获取影响行数
                logger.info(f"更新执行成功: {query}, 影响行数: {rowcount}")
                return rowcount
        except Exception as e:
            if self.connection:
                self.connection.rollback()
            logger.error(f"更新执行失败: {e}, SQL: {query}")
            raise

    def database_close(self):
        """关闭数据库连接"""
        if self.connection:
            self.connection.close()
            logger.info("数据库连接已关闭")
