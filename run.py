#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""统一执行入口（接口用例集 + UI 用例集）

用法：
    python run.py --list                      # 列出所有用例集与项目
    python run.py check-token                 # 预检 ACCESS_TOKEN_ADMIN 是否有效（约 2 小时过期）
    python run.py api 薪资包结算               # 只跑接口用例
    python run.py ui 薪资结算包收款包链路        # 只跑 UI 用例
    python run.py all                         # 两个用例集各跑默认项目
    python run.py api 审批流员工标签 -k 标签      # 追加 pytest 参数（-k / -m / -x / 文件名等）
    python run.py ui 薪资结算包收款包链路 --headless
    python run.py api 薪资包结算 --report       # 跑完自动生成 allure html 报告

约定：
    - 项目名写作位置参数；不写时取 .env 里的 API_PROJECT / UI_PROJECT
    - 环境变量 ENV（测试环境/预生产环境/生产环境）、DB_* 等统一读仓库根目录的 .env
"""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from core import paths  # noqa: E402


def _api_projects():
    """接口用例集项目名列表（不触发配置校验：临时清空 TEST_SUITE）"""
    old = os.environ.pop("TEST_SUITE", None)
    old_project = os.environ.get("CURRENT_PROJECT")
    os.environ["CURRENT_PROJECT"] = ""
    try:
        from api.config.setting import setting as api_setting
        return list(api_setting.TEST_FLIELOADS.keys())
    finally:
        if old is not None:
            os.environ["TEST_SUITE"] = old
        if old_project is None:
            os.environ.pop("CURRENT_PROJECT", None)
        else:
            os.environ["CURRENT_PROJECT"] = old_project


def _ui_projects():
    old = os.environ.pop("TEST_SUITE", None)
    old_project = os.environ.get("CURRENT_PROJECT")
    os.environ["CURRENT_PROJECT"] = ""
    try:
        from ui.config.settings import settings as ui_settings
        return list(ui_settings.PROJECT_CONFIGS.keys())
    finally:
        if old is not None:
            os.environ["TEST_SUITE"] = old
        if old_project is None:
            os.environ.pop("CURRENT_PROJECT", None)
        else:
            os.environ["CURRENT_PROJECT"] = old_project


def print_list():
    print("=" * 78)
    print("接口用例集（python run.py api <项目名>）")
    for name in _api_projects():
        print(f"    - {name}")
    print("UI 用例集（python run.py ui <项目名>）")
    for name in _ui_projects():
        print(f"    - {name}")
    print("=" * 78)
    print("环境变量 ENV：测试环境 / 预生产环境 / 生产环境（默认测试环境）")
    print(f"报告目录：{paths.REPORTS}")
    print(f"日志目录：{paths.LOGS}")
    print(f"Allure 结果：{paths.ALLURE_RESULTS}")


def _business_base():
    """业务平台地址（取 api 配置里 ENV 对应的 TEST_URL）"""
    try:
        from api.config.setting import setting
        base = setting.TEST_URL
        if isinstance(base, dict):                 # TEST_URL 是 {环境: 地址}
            return base.get(setting.ENV) or next(iter(base.values()))
        return base
    except SystemExit:
        return "https://test-admin.gsrtech.com"


def precheck_token(suite):
    """执行前预检 ACCESS_TOKEN_ADMIN；过期直接拦下，避免失败被误判成接口缺陷"""
    if os.getenv("TOKEN_CHECK", "true").lower() in ("false", "0", "no"):
        print("[token] 已跳过预检（--no-token-check / TOKEN_CHECK=false）")
        return 0
    from core.env import load_env
    from core.token_check import TOKEN_HELP, check_admin_token

    load_env()
    base = _business_base()
    ok, detail = check_admin_token(base, os.getenv("ACCESS_TOKEN_ADMIN", ""))
    if ok:
        print("[token] 预检通过：%s" % detail)
        return 0
    if ok is None:
        print("[token] 无法判定（%s）——继续执行，但失败时先怀疑登录态" % detail)
        return 0
    print("=" * 78)
    print("[token] 预检失败：%s" % detail)
    print(TOKEN_HELP.format(url=base))
    print("确认 token 没问题要强行执行：加 --no-token-check 或设 TOKEN_CHECK=false")
    print("=" * 78)
    return 2


def build_args(suite, project, extra):
    """组装 pytest 参数"""
    args = []
    if suite in ("api", "all"):
        args.append("api")
    if suite in ("ui", "all"):
        args.append("ui")
    args += ["--alluredir", paths.ALLURE_RESULTS, "--clean-alluredir"]
    args += extra
    return args


def generate_report():
    """生成 allure html 报告（本机装了 allure 命令行才会执行）"""
    out = os.path.join(paths.REPORTS, "allure-report")
    try:
        subprocess.run(["allure", "generate", paths.ALLURE_RESULTS, "-o", out, "--clean"], check=False)
        print(f"[报告] {os.path.join(out, 'index.html')}")
    except FileNotFoundError:
        print("[报告] 未安装 allure 命令行，跳过 html 生成（原始结果见 %s）" % paths.ALLURE_RESULTS)


def main(argv):
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(__doc__)
        return 0
    if argv[0] in ("-l", "--list", "list"):
        print_list()
        return 0
    if argv[0] == "lint":
        # 用例静态检查（执行前的第一道机器初审）
        from tools.lint_cases import main as lint_main
        return lint_main(argv[1:])
    if argv[0] in ("check-token", "token"):
        suite = "api"
        os.environ["TEST_SUITE"] = suite
        return precheck_token(suite)
    if argv[0] == "zentao":
        # 执行结果 → 禅道提单（默认只生成草稿）
        from tools.zentao_report import main as zentao_main
        return zentao_main(argv[1:])

    suite = argv[0].lower()
    if suite not in ("api", "ui", "all"):
        print(f"[错误] 未知用例集 {suite!r}，只能是 api / ui / all（python run.py --list 查看）")
        return 2

    project = None
    extra = []
    want_report = False
    idx = 1
    while idx < len(argv):
        arg = argv[idx]
        if arg == "--report":
            want_report = True
        elif arg == "--headless":
            os.environ["HEADLESS"] = "true"
        elif arg == "--headed":
            os.environ["HEADLESS"] = "false"
        elif arg == "--no-token-check":
            os.environ["TOKEN_CHECK"] = "false"
        elif arg.startswith("-"):
            # 其余参数原样交给 pytest（含它后面的值）
            if "=" in arg:
                extra.append(arg)
            else:
                extra.append(arg)
                if idx + 1 < len(argv) and not argv[idx + 1].startswith("-") and arg in (
                        "-k", "-m", "-n", "--maxfail", "--timeout"):
                    extra.append(argv[idx + 1])
                    idx += 1
        elif project is None:
            project = arg
        else:
            extra.append(arg)
        idx += 1

    # 用例集与项目名注入（配置层只读环境变量）
    os.environ["TEST_SUITE"] = suite
    if suite == "api":
        os.environ["API_PROJECT"] = project or os.getenv("API_PROJECT", "")
    elif suite == "ui":
        os.environ["UI_PROJECT"] = project or os.getenv("UI_PROJECT", "")
    else:
        # all：两个用例集各跑 .env 里约定的默认项目
        if project:
            print("[提示] all 不使用位置参数的项目名，已忽略 %r；请用 .env 的 API_PROJECT / UI_PROJECT 指定" % project)
        if not os.getenv("API_PROJECT"):
            print("[错误] all 需要指定接口用例项目：设置 .env 的 API_PROJECT，或先单独跑 python run.py api <项目名>")
            return 2

    code = precheck_token(suite)
    if code:
        return code

    paths.ensure_dirs()
    print("=" * 78)
    print(f"用例集：{suite}    项目：{project or '(取 .env 默认)'}    环境：{os.getenv('ENV', '测试环境')}")
    print("=" * 78)

    import pytest
    code = pytest.main(build_args(suite, project, extra))
    if want_report:
        generate_report()
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
