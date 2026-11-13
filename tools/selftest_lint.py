#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""lint_cases 自测：生成「故意埋错」的用例文件，验证每条规则都能被触发

用法：python tools/selftest_lint.py
      全部规则命中 → 打印 PASS 并退出码 0；有规则失效 → 打印缺失项并退出码 1
只写入临时目录（reports/_lint_selftest/），不碰正式用例文件。
"""
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from core import paths  # noqa: E402

TMP = os.path.join(paths.REPORTS, "_lint_selftest")

API_HEADERS = ["case_id", "name", "headers", "method", "url", "data", "response",
               "extract", "validata", "result", "retry"]


def build_api_fixture(path):
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "测试执行"
    ws.append(API_HEADERS)

    def row(case_id, name, method, url, data, extract=None, validata=None, retry=None):
        ws.append([case_id, name, "{}", method, url, data, None, extract, validata, None, retry])

    # 正常用例：不应报错
    row("1", "管理端｜正常用例", "POST", "/api/center/x", '{"a": 1}', None, '{"$.code": 200}')
    # method 拼写错误
    row("2", "管理端｜method 拼错", "PSOT", "/api/center/x", "{}", None, '{"$.code": 200}')
    # 引用未定义变量
    row("3", "管理端｜变量未定义", "POST", "/api/center/x", '{"a": "${no_such_var}"}', None, '{"$.code": 200}')
    # retry 非法
    row("4", "管理端｜retry 非法", "POST", "/api/center/x", "{}", None, '{"$.code": 200}', "abc")
    # 断言不是 JSON
    row("5", "管理端｜断言非 JSON", "POST", "/api/center/x", "{}", None, "not a json")
    # 断言键不是 jsonpath
    row("6", "管理端｜断言键非 jsonpath", "POST", "/api/center/x", "{}", None, '{"code": 200}')
    # extract 不是 JSON
    row("7", "管理端｜extract 非 JSON", "POST", "/api/center/x", "{}", "bad json", '{"$.code": 200}')
    # db_update：SQL 写进了断言列
    row("8", "管理端｜db_update 断言写错", "db_update", None, "UPDATE t SET a=1", None, "SET autocommit=1")
    # db_select：没写 SQL
    row("9", "管理端｜db_select 缺 SQL", "db_select", None, None, None, "status=2")
    # editexcel：data 为空对象
    row("10", "管理端｜editexcel 缺字段", "editexcel", None, "{}", None, None)
    # case_id 为空
    row(None, "管理端｜case_id 为空", "POST", "/api/center/x", "{}", None, '{"$.code": 200}')
    wb.save(path)
    wb.close()


def build_ui_fixture(path):
    cases = {
        "test_cases": [
            {
                "id": "c1", "name": "自测-正常步骤+埋错步骤", "page": "gsr_admin_page",
                "steps": [
                    {"step_name": "正常输入", "element": "username_input", "action": "input", "data": "abc"},
                    {"step_name": "action 拼错", "element": "username_input", "action": "clikc", "data": ""},
                    {"step_name": "元素不存在", "element": "no_such_element_xyz", "action": "click", "data": ""},
                    {"step_name": "check_exists 值非法", "element": "username_input",
                     "action": "check_exists", "data": "有"},
                    {"step_name": "wait 非数字", "element": None, "action": "wait", "data": "abc"},
                    {"step_name": "save_text 变量名非法", "element": "username_input",
                     "action": "save_text", "data": "1bad name"},
                    {"step_name": "占位符未加引号", "element": "username_input",
                     "action": "input", "data": {"username": None}},
                    {"step_name": "接口侧写法的变量", "element": "username_input",
                     "action": "input", "data": "Hi ${no_such_var}"},
                    {"step_name": "未定义变量", "element": "username_input",
                     "action": "input", "data": "Hi {no_such_var}"},
                    {"step_name": "upload 缺 data", "element": "username_input", "action": "upload"},
                ],
            },
            {"id": "c1", "name": "自测-id 重复", "page": "gsr_admin_page", "steps": []},
            {"id": "c3", "name": "自测-缺 page", "steps": []},
        ]
    }
    import yaml
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(cases, f, allow_unicode=True, sort_keys=False)


def run_lint(path):
    cmd = [sys.executable, os.path.join(ROOT, "tools", "lint_cases.py"),
           "--file", path, "--format", "json"]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", cwd=ROOT)
    try:
        return json.loads(proc.stdout)
    except ValueError:
        print("lint 输出无法解析为 JSON：\n", proc.stdout[-2000:], proc.stderr[-2000:])
        return {"issues": []}


def main():
    os.makedirs(TMP, exist_ok=True)
    api_file = os.path.join(TMP, "selftest_api.xlsx")
    ui_file = os.path.join(TMP, "selftest_ui.yaml")
    build_api_fixture(api_file)
    build_ui_fixture(ui_file)

    api_codes = {i["code"] for i in run_lint(api_file)["issues"]}
    ui_codes = {i["code"] for i in run_lint(ui_file)["issues"]}

    expect_api = {"API-METHOD", "API-VAR", "API-RETRY", "API-ASSERT", "API-EXTRACT",
                  "API-DB-ASSERT", "API-DB", "API-EDITEXCEL", "API-ID"}
    expect_ui = {"UI-ACTION", "UI-ELEMENT", "UI-ACTION-DATA", "UI-VAR", "UI-VAR-SYNTAX",
                 "UI-YAML-TYPE", "UI-ID", "UI-PAGE"}

    missing_api = sorted(expect_api - api_codes)
    missing_ui = sorted(expect_ui - ui_codes)
    print("接口侧命中规则：", "、".join(sorted(api_codes)) or "无")
    print("UI  侧命中规则：", "、".join(sorted(ui_codes)) or "无")

    # 正常用例不应被误报
    if any(i["level"] == "ERROR" and "正常用例" in str(i.get("case", "")) for i in run_lint(api_file)["issues"]):
        print("\n[FAIL] 正常用例被误报为错误")
        return 1

    if missing_api or missing_ui:
        if missing_api:
            print(f"\n[FAIL] 接口侧规则未命中：{'、'.join(missing_api)}")
        if missing_ui:
            print(f"\n[FAIL] UI 侧规则未命中：{'、'.join(missing_ui)}")
        return 1

    print("\n[PASS] 全部规则命中，且正常用例无误报")
    return 0


if __name__ == "__main__":
    sys.exit(main())
