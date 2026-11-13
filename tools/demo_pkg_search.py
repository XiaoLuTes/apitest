#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""场景 → 证据 → 提单 示例：薪资包管理「按薪资包ID搜索不存在的关键字」

这是"给 AI/人看的模板脚本"：把一次真实 UI 操作完整记录成证据包（步骤 + 接口返回 + 截图），
满足触发条件时直接提一张带证据的缺陷单。

触发条件：搜索结果为空（列表 0 行）
用法：
    python tools/demo_pkg_search.py                    # 只采集证据 + 出草稿
    python tools/demo_pkg_search.py --submit            # 采集后直接提单
    python tools/demo_pkg_search.py --code 测试不存在code --submit
"""
import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

os.environ.setdefault("TEST_SUITE", "ui")
os.environ.setdefault("UI_PROJECT", "薪资包管理查询")
os.environ.setdefault("HEADLESS", "true")

from core import paths  # noqa: E402
from core.env import load_env  # noqa: E402

load_env()

import tools.evidence_bug as evidence_bug  # noqa: E402
from ui.pages.payroll_package_page import PayrollPackagePage  # noqa: E402
from ui.utils.browser import BrowserEngine  # noqa: E402
from ui.utils.evidence import EvidenceRecorder  # noqa: E402
from ui.utils.page_manager import PageManager  # noqa: E402


def run(code, submit=False):
    engine = BrowserEngine()
    page = engine.start_browser()
    recorder = EvidenceRecorder(
        page, api_keywords=["/payrollSalaryPackage/list"],
        title=f"薪资包管理-按薪资包ID搜索「{code}」返回空列表且无结果提示",
        case_id="PKG-SEARCH-NOTFOUND",
    ).start()
    try:
        manager = PageManager(page)
        pkg = PayrollPackagePage("payroll_package_page", page)
        pkg.set_page_manager(manager)
        manager.pages["payroll_package_page"] = pkg

        recorder.step("打开 管理端 → Payroll → 算薪 → 薪资包管理",
                      action="open", note="菜单路径：Payroll / 算薪 / 薪资包管理")
        pkg.open_package_management()

        recorder.step("在「薪资包ID」输入框输入不存在的关键字", action="input",
                      element="pkg_code_input", data=code)
        data = pkg.query_by_package_code(code)

        rows = pkg.get_table_rows()
        empty_text = pkg.get_empty_text()
        recorder.step("点击「搜 索」并等待列表接口返回", action="click", element="search_button")
        recorder.step("查看列表结果", action="check",
                      note=f"表格 {len(rows)} 行；空状态文案：{empty_text or '无'}")
        shot = recorder.screenshot(f"薪资包管理-搜索{code}-列表为空")
        recorder.stop()

        api = recorder.last_api("/payrollSalaryPackage/list")
        total = data.get("total") if isinstance(data, dict) else None
        triggered = len(rows) == 0

        print("\n=== 采集结果 ===")
        print(f"关键字      : {code}")
        print(f"列表行数    : {len(rows)}")
        print(f"接口 total  : {total}")
        print(f"空状态文案  : {empty_text or '（无）'}")
        print(f"截图        : {shot}")
        print(f"触发提单    : {'是' if triggered else '否（列表有数据，不符合触发条件）'}")

        extra = {
            "precondition": "管理端已登录（卢毅/Louie 账号）；环境：测试环境；"
                            "页面：Payroll → 算薪 → 薪资包管理",
            "expected": "搜索一个不存在的薪资包ID时，列表应为空并给出明确的结果提示"
                        "（如「未找到匹配的薪资包」toast 或表格空状态文案），接口应返回 total=0 且不返回其他数据",
            "actual": f"列表返回空（{len(rows)} 行），页面空状态文案为「{empty_text or '无'}」，"
                      f"接口返回 total={total}；未出现任何「未找到匹配结果」类提示",
            "expect": "搜索不存在的薪资包ID时，列表为空并给出明确的空结果提示（toast 或空状态文案）；"
                      "接口 total=0，且不返回其他客户/其他薪资包的数据",
            "severity": 4, "pri": 4, "type": "others",
            "keywords": "自动化,演示",
            "api_keyword": "payrollSalaryPackageCode",
        }
        evidence = recorder.to_dict(extra=extra)
        ev_path = recorder.dump(extra=extra)
        print(f"证据文件    : {ev_path}")

        if not triggered:
            print("\n不符合触发条件，不生成缺陷单。")
            return 0

        bug_id = evidence_bug.file_bug(evidence, submit=submit,
                                       severity=4, pri=4, bug_type="others")
        if bug_id:
            print(f"\n缺陷单已创建：http://172.21.100.100:8101/zentao/bug-view-{bug_id}.html")
        return 0
    finally:
        recorder.stop()
        engine.stop_browser()


def main():
    parser = argparse.ArgumentParser(description="薪资包搜索不存在的关键字 → 证据 → 提单")
    parser.add_argument("--code", default="测试不存在code", help="要搜索的薪资包ID关键字")
    parser.add_argument("--submit", action="store_true", help="采集后直接提单")
    args = parser.parse_args()
    return run(args.code, submit=args.submit)


if __name__ == "__main__":
    sys.exit(main())
