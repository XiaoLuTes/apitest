import pytest
from common import excel_read
from config.setting import setting
from common.executor import Executor


fileload = setting.TEST_FLIELOAD
# 测试用例文件路径
test_url = setting.TEST_URL
# 测试环境路径
class TestFile:
    @pytest.fixture(scope="function", autouse=True)
    def setup_test(self):
        """测试类级别初始化"""
        self.executor = Executor()
        yield

    # excel用例执行
    @pytest.mark.parametrize('file', excel_read.Excel().read_excel(fileload))
    def test_excel_cloud(self, file):
        self.executor.execute(file)
