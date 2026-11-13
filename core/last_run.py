# -*- coding: utf-8 -*-
"""最近一次执行的指针（reports/last_run.json）

解决的问题：提单时"取最近一次结果"可能拿到几天前的旧结果。
每次 `run.py api|ui|all` 结束写一条记录；`run.py zentao` 默认只认这条记录，
并打印「使用的是哪个时间点的结果」，超过保鲜期才允许 `--allow-stale` 强行使用。

记录结构：
    {
      "time": "2026-11-13 18:36:37",     # 本次执行结束时间
      "epoch": 1763028397.1,
      "suite": "api",                     # api / ui / all
      "project": "薪资包管理查询",
      "env": "测试环境",
      "exit_code": 0,
      "results": ["reports/results/api/xxx.xlsx"]
    }
"""
import json
import os
import time

from core import paths

FILE = os.path.join(paths.REPORTS, "last_run.json")


def collect_results(started_at, suites=("api", "ui")):
    """收集本次执行产生/更新的结果文件（mtime >= 开始时间 - 2 秒）"""
    found = []
    for suite in suites:
        directory = paths.RESULTS_API if suite == "api" else paths.RESULTS_UI
        if not os.path.isdir(directory):
            continue
        for name in os.listdir(directory):
            full = os.path.join(directory, name)
            if not os.path.isfile(full):
                continue
            if name.startswith("_"):          # 自检/临时文件不算
                continue
            if os.path.getmtime(full) >= started_at - 2:
                found.append(full)
    return found


def write_run(suite, project, env, exit_code, started_at, results=None):
    paths.ensure_dirs()
    record = {
        "time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "epoch": time.time(),
        "suite": suite,
        "project": project or "",
        "env": env or "",
        "exit_code": exit_code,
        "results": results if results is not None else collect_results(
            started_at, ("api", "ui") if suite == "all" else (suite,)),
    }
    try:
        with open(FILE, "w", encoding="utf-8") as f:
            json.dump(record, f, ensure_ascii=False, indent=2)
    except OSError as e:
        print("[last_run] 写入失败：%s" % e)
    return record


def read_last_run(max_age_hours=24.0):
    """返回 (record, age_hours)；没有记录返回 (None, None)"""
    if not os.path.isfile(FILE):
        return None, None
    try:
        with open(FILE, encoding="utf-8") as f:
            record = json.load(f)
    except (OSError, ValueError):
        return None, None
    age = (time.time() - float(record.get("epoch") or 0)) / 3600.0
    return record, age


def print_record(record, age):
    files = record.get("results") or []
    print("[结果来源] %s（%.1f 小时前）｜用例集 %s｜项目 %s｜环境 %s｜退出码 %s"
          % (record.get("time"), age, record.get("suite"), record.get("project") or "-",
             record.get("env") or "-", record.get("exit_code")))
    for f in files:
        print("            - %s" % os.path.basename(f))
    if not files:
        print("            （本次执行没有产生结果文件）")
