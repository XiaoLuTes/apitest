"""pytest 根配置：只做两个用例集共用的初始化，具体夹具在 api/conftest.py、ui/conftest.py 里。

用例集选择：环境变量 TEST_SUITE = api / ui / all（由 run.py 设置，直接跑 pytest 时默认 all）
"""
import os
import sys

from core import paths

# 保证仓库根目录在 sys.path 里（不管从哪个工作目录执行）
if paths.ROOT not in sys.path:
    sys.path.insert(0, paths.ROOT)

# 统一创建报告目录
paths.ensure_dirs()


def pytest_configure(config):
    suite = os.getenv("TEST_SUITE", "all")
    if suite not in ("api", "ui", "all"):
        raise SystemExit(f"[配置错误] TEST_SUITE={suite!r} 非法，只能是 api / ui / all")
    project = os.getenv("CURRENT_PROJECT", "")
    config._suite_banner = f"用例集：{suite}    项目：{project or '(未指定)'}    环境：{os.getenv('ENV', '测试环境')}"


def pytest_report_header(config):
    return getattr(config, "_suite_banner", None)
