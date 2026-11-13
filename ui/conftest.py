import os
import sys

# 兼容 PyCharm 直接右键运行（工作目录可能是 api/ 或 ui/ 子目录）：
# 保证仓库根目录在 sys.path 里，才能 import api.* / ui.* / core.*
_ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT_DIR not in sys.path:
    sys.path.insert(0, _ROOT_DIR)

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
