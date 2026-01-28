import pytest
from common import yaml_util
from common.logger import logger
from common.database import DatabaseUtils


@pytest.fixture(scope="session", autouse=True)   # autouse=True  自动执行
def execute_session():
    logger.info("=========================== 接口测试开始 ===========================")
    yaml_util.clean_yaml()
    yaml_util.write_yaml(yaml_util.read_yaml_all())
    db_instance = DatabaseUtils()
    yield
    if db_instance.connection is not None:
        db_instance.close_database_connection()
        logger.info(f"测试结束，关闭数据库链接")
    else:
        logger.info(f"无数据库操作，无需关闭数据库链接")
    logger.info("=========================== 接口测试结束 ===========================\n")
