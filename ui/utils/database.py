import pymysql
from pymysql import cursors
from ui.utils.logger import logger
from typing import List, Dict, Any
from ui.config.settings import settings


class DatabaseUtils:
    def __init__(self):
        self.host = str(settings.DB_HOST)
        self.user = str(settings.DB_USER)
        self.password = str(settings.DB_PASSWORD)
        self.database = str(settings.DB_NAME)
        self.port = int(settings.DB_PORT)
        self.timeout = settings.DB_TIMEOUT
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
            raise

    def execute_query(self, query: str, params=None) -> List[Dict[str, Any]]:
        """执行查询语句"""
        try:
            if self.connection is None:
                self.connect()

            with self.connection.cursor() as cursor:
                cursor.execute(query, params or ())
                result = cursor.fetchall()
                logger.info(f"SQL查询执行成功")
                return result
        except Exception as e:
            logger.error(f"SQL查询失败: {e}, SQL: {query}")
            raise

    def execute_update(self, query: str, params=None) -> int:
        """执行更新语句"""
        try:
            if self.connection is None:
                self.connect()

            with self.connection.cursor() as cursor:
                cursor.execute(query, params or ())
                self.connection.commit()
                rowcount = cursor.rowcount
                logger.info(f"SQL更新成功，影响行数: {rowcount}")
                return rowcount
        except Exception as e:
            if self.connection:
                self.connection.rollback()
            logger.error(f"SQL更新失败: {e}, SQL: {query}")
            raise

    def database_close(self):
        """关闭数据库连接"""
        if self.connection:
            self.connection.close()
            self.connection = None
            logger.info("数据库连接已关闭")
