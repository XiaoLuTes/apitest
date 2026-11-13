import pytest
from ui.utils.browser import BrowserEngine
from ui.config.settings import settings
from ui.utils.common import VariableStore

# 运行开始前：预置 settings 常用变量（username/password/customer/owner/replace_num）
VariableStore.preload(settings)

@pytest.fixture(scope="session")
def browser():
    engine = BrowserEngine()
    page = engine.start_browser()
    yield page
    engine.stop_browser()
    VariableStore.dump()
