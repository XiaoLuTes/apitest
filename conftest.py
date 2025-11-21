import pytest
import yaml_util
import logger
from common import yaml_util

@pytest.fixture(scope="session", autouse=True)   # autouse=True  自动执行
def execute_session():
    logger.logger.info("=========================== 接口测试开始 ===========================")
    yaml_util.clean_yaml()
    yaml_util.write_yaml(yaml_util.read_yaml_all())
    yield
    logger.logger.info("=========================== 接口测试结束 ===========================\n")
