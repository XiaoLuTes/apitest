"""统一路径定义

所有路径都以本文件为基准计算成绝对路径，因此框架可以在任意工作目录下执行
（例如 `python run.py api`、pytest 单文件调试、PyCharm 里直接右键运行）。

目录约定：
    <ROOT>                  仓库根目录（autotest）
    <ROOT>/api              接口自动化用例集
    <ROOT>/ui               UI（Playwright）自动化用例集
    <ROOT>/reports          所有产物（日志 / 结果 / 下载 / 截图 / allure）
"""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
API_ROOT = os.path.join(ROOT, "api")
UI_ROOT = os.path.join(ROOT, "ui")

# ---- 报告与产物目录 ----
REPORTS = os.path.join(ROOT, "reports")
LOGS = os.path.join(REPORTS, "logs")
LOGS_ERROR = os.path.join(REPORTS, "logs_error")
RESULTS = os.path.join(REPORTS, "results")
RESULTS_API = os.path.join(RESULTS, "api")
RESULTS_UI = os.path.join(RESULTS, "ui")
DOWNLOADS = os.path.join(REPORTS, "downloads")
SCREENSHOTS = os.path.join(REPORTS, "screenshots")
ALLURE_RESULTS = os.path.join(REPORTS, "allure-results")
AUTH_STATE = os.path.join(REPORTS, "auth")

ALL_DIRS = (REPORTS, LOGS, LOGS_ERROR, RESULTS, RESULTS_API, RESULTS_UI,
            DOWNLOADS, SCREENSHOTS, ALLURE_RESULTS, AUTH_STATE)


def ensure_dirs(*dirs):
    """批量创建目录（默认创建全部报告目录）"""
    for d in (dirs or ALL_DIRS):
        if d:
            os.makedirs(d, exist_ok=True)


def resolve(path, base=None):
    """相对路径按 base（默认仓库根目录）解析为绝对路径；绝对路径原样返回"""
    if not path:
        return path
    if os.path.isabs(path):
        return os.path.normpath(path)
    return os.path.normpath(os.path.join(base or ROOT, path))
