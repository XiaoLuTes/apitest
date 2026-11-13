import pytest
import allure
from ui.utils.logger import logger
from ui.utils.page_manager import PageManager
from ui.utils.yaml_load import YamlLoad
from ui.utils.executor import Executor

data_loader = YamlLoad()
test_cases = data_loader.load_test_cases()

@allure.feature("YAML驱动登录测试")
class TestLoginFromYAML:

    @pytest.fixture(autouse=True)
    def setup(self, browser):
        self.page = browser
        self.page_manager = PageManager(self.page)
        self.executor = Executor(self.page, self.page_manager)
        logger.info("测试初始化完成")
        yield

    @pytest.mark.parametrize("test_case", test_cases, ids=[tc["id"] for tc in test_cases])
    def test_login_scenarios(self, test_case):
        allure.dynamic.title(f"{test_case['id']} - {test_case['name']}")
        result = self.executor.execute_test_case(test_case)
        assert result, "用例执行失败"
