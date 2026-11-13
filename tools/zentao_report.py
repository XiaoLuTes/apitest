#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""执行结果 → 禅道提单（统一格式：步骤 + 接口请求/返回 + 截图）

两条入口都走同一套模板（tools/evidence_bug.py）：
    1. 有证据包（reports/evidence/*.json，UI/API 用例失败时自动落盘）→ 直接用它
    2. 没证据包 → 从结果文件重建：接口信息取 result/url/data 列，
       没有截图时把"请求 + 返回 + 断言差异"渲染成一张证据图，保证每单都有接口和截图
提单字段（对齐公司禅道）：产品 1 / 模块 393 / 严重程度 3 / 优先级 3 / 类型 codeerror /
影响版本 trunk / 反馈者=登录账号 / 指派 ZENTAO_ASSIGNEE；附件走页面上传并内联引用。

用法：
    python run.py zentao --probe                    # 探测禅道
    python run.py zentao                            # 最近一次执行结果 → 草稿
    python run.py zentao --submit --yes             # 真提交
    python run.py zentao --from reports/results/api/x.xlsx
    python run.py zentao --repeat 1                 # 放宽复现次数（默认 2）
    python run.py zentao --include-env              # 连环境类失败一起提（默认不提）
"""
import argparse
import glob
import json
import os
import re
import time
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from core import paths  # noqa: E402
from core.env import load_env  # noqa: E402

load_env()

import tools.evidence_bug as evidence_bug  # noqa: E402

EVIDENCE_DIR = os.path.join(paths.REPORTS, "evidence")


# ============================================================================
# 1. 读执行结果
# ============================================================================


def _read_api_failures(xlsx_path):
    import openpyxl

    failures = []
    wb = openpyxl.load_workbook(xlsx_path, data_only=True)
    try:
        for sheet in wb.sheetnames:
            ws = wb[sheet]
            header = [str(c.value).strip() if c.value is not None else "" for c in ws[1]]
            if "result" not in header:
                continue
            idx = {name: i for i, name in enumerate(header) if name}
            for row in ws.iter_rows(min_row=2, values_only=True):
                result = row[idx["result"]] if idx["result"] < len(row) else None
                if not isinstance(result, str) or not result.strip().startswith("失败"):
                    continue

                def cell(name):
                    pos = idx.get(name)
                    if pos is None or pos >= len(row):
                        return ""
                    value = row[pos]
                    return "" if value is None else str(value)

                failures.append({
                    "suite": "api",
                    "source": os.path.basename(xlsx_path),
                    "sheet": sheet,
                    "case_id": cell("case_id"),
                    "name": cell("name"),
                    "reason": result.replace("失败：", "").replace("失败:", "").strip(),
                    "method": cell("method"),
                    "url": cell("url"),
                    "request_body": cell("data"),
                    "response": cell("response"),
                })
    finally:
        wb.close()
    return failures


def _read_ui_failures(yaml_path):
    import yaml

    with open(yaml_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    failures = []
    for case in data.get("test_cases") or []:
        result = str(case.get("result") or "")
        if not result.startswith("失败"):
            continue
        failures.append({
            "suite": "ui",
            "source": os.path.basename(yaml_path),
            "sheet": "",
            "case_id": str(case.get("id") or ""),
            "name": str(case.get("name") or ""),
            "reason": result.replace("失败:", "").replace("失败：", "").strip(),
            "method": "", "url": "", "request_body": "", "response": "",
        })
    return failures


def latest_result_files():
    api = sorted(glob.glob(os.path.join(paths.RESULTS_API, "*.xlsx")), key=os.path.getmtime)
    ui = sorted(glob.glob(os.path.join(paths.RESULTS_UI, "*.yaml")), key=os.path.getmtime)
    return (api[-1] if api else None), (ui[-1] if ui else None)


def collect_failures(source=None):
    """source 可以是单个文件、文件列表或 None（默认取最近一次执行的结果）"""
    if source is None:
        files = [f for f in latest_result_files() if f]
    elif isinstance(source, (list, tuple)):
        files = list(source)
    else:
        files = [source]
    failures = []
    for path in files:
        if not os.path.isfile(path):
            print(f"[提示] 结果文件不存在：{path}")
            continue
        if path.lower().endswith((".xlsx", ".xlsm")):
            failures.extend(_read_api_failures(path))
        elif path.lower().endswith((".yaml", ".yml")):
            failures.extend(_read_ui_failures(path))
        else:
            print(f"[提示] 不认识的结果文件类型：{path}")
    return failures, [f for f in files if os.path.isfile(f)]


# ============================================================================
# 2. 失败分类 + 稳定性
# ============================================================================

ENV_PATTERNS = (
    r"110106", r"没有访问权限", r"令牌", r"\b401\b", r"\b403\b",
    r"超时", r"Timeout", r"timed out", r"连接", r"Connection", r"\b50[234]\b", r"网络",
)
CASE_PATTERNS = (
    r"未定义", r"未查询到", r"不存在", r"无法打开", r"JSON", r"extract",
    r"缺少", r"元素查找超时", r"参数错误",
)
ASSERT_PATTERNS = (
    r"断言", r"期望", r"实际", r"文本不匹配", r"输入验证失败", r"元素应",
    r"SQL行数", r"字段断言", r"不匹配",
)


# 强断言特征：先判这些，避免"预期包含'xxx不存在'".这句里带"不存在"被误判成用例问题
STRONG_ASSERT_PATTERNS = (
    r"断言项\[", r"文本不匹配", r"输入验证失败", r"元素应", r"SQL行数",
    r"期望值[:：]", r"预期包含", r"断言失败",
)


def classify(reason):
    text = str(reason or "")
    for pat in STRONG_ASSERT_PATTERNS:
        if re.search(pat, text):
            return "ASSERT"
    for pat in ENV_PATTERNS:
        if re.search(pat, text):
            return "ENV"
    for pat in CASE_PATTERNS:
        if re.search(pat, text):
            return "CASE"
    for pat in ASSERT_PATTERNS:
        if re.search(pat, text):
            return "ASSERT"
    return "UNKNOWN"


def _all_result_files():
    api = sorted(glob.glob(os.path.join(paths.RESULTS_API, "*.xlsx")), key=os.path.getmtime)
    ui = sorted(glob.glob(os.path.join(paths.RESULTS_UI, "*.yaml")), key=os.path.getmtime)
    return api + ui


_BATCH_STAMP = re.compile(r"(\d{8}_\d{6})")


def batch_of(path):
    """结果文件所属的执行批次：文件名里的 YYYYmmdd_HHMMSS

    命名见 api/common/excel_read.py::save_results()（同一轮执行的所有结果文件共用
    同一个时间戳）与 ui/utils/yaml_load.py（YamlLoad.batch_id）。
    取不到时间戳时用文件修改时间（分钟粒度）兜底。
    """
    # 用例文件名里也可能带日期，取最后一个时间戳（执行批次号由框架追加在末尾）
    matched = _BATCH_STAMP.findall(os.path.basename(path))
    if matched:
        return matched[-1]
    return time.strftime("%Y%m%d_%H%M", time.localtime(os.path.getmtime(path)))


def _recent_result_files(days=0, now=None):
    """最近 days 天内的结果文件（days<=0 表示不限）"""
    files = _all_result_files()
    if days and days > 0:
        cutoff = (now or time.time()) - days * 86400
        files = [f for f in files if os.path.getmtime(f) >= cutoff]
    return files


def history_days(default=30):
    """历史统计窗口（天），0 = 不限；可用 ZENTAO_HISTORY_DAYS 覆盖"""
    raw = os.getenv("ZENTAO_HISTORY_DAYS", str(default))
    try:
        return max(0, int(str(raw).split("#")[0].strip()))
    except (TypeError, ValueError):
        print("[提示] ZENTAO_HISTORY_DAYS=%r 不是整数，按 %d 天处理" % (raw, default))
        return default


def history_failure_counts(days=None):
    """历史失败次数：按「执行批次」去重后统计（同一批次内只算 1 次）

    批次 = 一次执行（结果文件名里的 YYYYmmdd_HHMMSS）。作用：
      1) 同一轮执行里重复出现、或同一份结果被重复读取，都不会把次数刷高；
      2) 叠加时间窗（默认 30 天），避免几周前已修复的旧失败一直算进「历史」，
         让 --repeat 的「稳定复现」判定只反映近期情况。
    """
    if days is None:
        days = history_days()
    batches = {}                                 # (suite, case_id, name) -> {批次, ...}
    for path in _recent_result_files(days):
        batch = batch_of(path)
        try:
            items = (_read_api_failures(path) if path.lower().endswith((".xlsx", ".xlsm"))
                     else _read_ui_failures(path))
        except Exception:                        # noqa: BLE001
            continue
        for item in items:
            key = (item["suite"], item["case_id"], item["name"])
            batches.setdefault(key, set()).add(batch)
    return {key: len(value) for key, value in batches.items()}


# ============================================================================
# 3. 组装证据包（优先用执行时落的证据，其次从结果重建）
# ============================================================================


def _load_evidence_pool():
    """按修改时间倒序加载所有证据包"""
    pool = []
    for path in sorted(glob.glob(os.path.join(EVIDENCE_DIR, "*.json")), key=os.path.getmtime,
                       reverse=True):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            data["_path"] = path
            pool.append(data)
        except Exception:                        # noqa: BLE001
            continue
    return pool


def _match_evidence(failure, pool):
    case_id = str(failure.get("case_id") or "").strip()
    name = str(failure.get("name") or "").strip()
    for ev in pool:
        ev_case = str(ev.get("case_id") or "").strip()
        ev_title = str(ev.get("title") or "").strip()
        if case_id and ev_case and (ev_case == case_id or ev_case.endswith(case_id)):
            return ev
        if name and (ev_title == name or name in ev_title):
            return ev
    return None


def build_evidence(failure):
    """证据包 + 失败上下文 → 提单用 evidence"""
    pool = _load_evidence_pool()
    found = _match_evidence(failure, pool)
    if found:
        evidence = dict(found)
        evidence.pop("_path", None)
        evidence.setdefault("case_ref", {})
        if not evidence.get("screenshots"):
            evidence["screenshots"] = []
    else:
        api_calls = []
        if failure.get("url"):
            api_calls.append({
                "method": failure.get("method") or "GET",
                "url": failure["url"],
                "request_body": failure.get("request_body") or "",
                "status": None,
                "response": failure.get("response") or "",
            })
        evidence = {
            "title": failure.get("name") or failure.get("case_id"),
            "case_id": failure.get("case_id"),
            "env": os.getenv("ENV", "测试环境"),
            "precondition": (f"自动化用例 {failure.get('case_id')} 执行失败；"
                             f"用例文件：{failure.get('source')}（{failure.get('sheet') or failure.get('suite')}）"),
            "steps": [
                {"name": f"执行用例：{failure.get('case_id')} {failure.get('name')}", "action": "case"},
                {"name": "执行失败，记录失败现场（无独立证据包，由结果文件重建）", "action": "note"},
            ],
            "api_calls": api_calls,
            "screenshots": [],
        }

    # 期望 / 实际：证据里没有就用失败原因补齐（保证单子可读）
    if not evidence.get("expect"):
        expects = re.findall(r"期望值?[:：]\s*([^|；;]+)", failure.get("reason") or "")
        evidence["expect"] = "；".join(x.strip() for x in expects[:5]) or "与用例断言一致"
    if not evidence.get("actual"):
        evidence["actual"] = failure.get("reason") or ""
    evidence["env"] = evidence.get("env") or os.getenv("ENV", "测试环境")

    # 截图规则：UI 单带页面截图；接口单不截图（内容已在 [步骤]/[接口]/[请求参数]/[接口返回] 里）
    evidence["screenshots"] = [p for p in evidence.get("screenshots") or [] if os.path.isfile(p)]
    if not evidence["screenshots"] and failure.get("suite") != "api":
        print("[提示] 该 UI 失败没有采到截图（可能未走 UI 执行器），单子里将没有图")
    return evidence


# ============================================================================
# 4. 探测
# ============================================================================


def probe():
    from core.zentao import ZentaoClient, ZentaoError

    print("=" * 70)
    try:
        client = ZentaoClient.from_env()
    except ZentaoError as e:
        print(e)
        return 2
    print(f"禅道地址：{client.url}")
    try:
        client.login()
        print("登录结果：成功")
    except ZentaoError as e:
        print(f"登录结果：失败 → {e}")
        return 2
    for label, func in (("当前用户", client.whoami), ("产品列表", client.products)):
        try:
            print(f"{label}：{json.dumps(func(), ensure_ascii=False)[:200]}")
        except ZentaoError as e:
            print(f"{label}：不可用 → {e}")
    print("提单默认值：产品 {} / 模块 {} / 严重程度 {} / 优先级 {} / 类型 {} / 影响版本 {}".format(
        os.getenv("ZENTAO_PRODUCT", "1"), os.getenv("ZENTAO_MODULE", "393"),
        os.getenv("ZENTAO_SEVERITY", "3"), os.getenv("ZENTAO_PRI", "3"),
        os.getenv("ZENTAO_TYPE", "codeerror"), os.getenv("ZENTAO_OPENED_BUILD", "trunk")))
    return 0


# ============================================================================
# 5. 入口
# ============================================================================




# ============================================================================
# 结果来源：只认本次执行（reports/last_run.json），过期需 --allow-stale
# ============================================================================
ATTENDANCE_KEYWORDS = ("假勤", "请假", "加班", "销假", "考勤", "审批流", "审批条件", "排班",
                       "leave", "attendance", "overtime", "holiday")


PAYROLL_KEYWORDS = ("薪资", "结算", "收款", "payroll", "Payroll")


def _as_int(value, default):
    """把 env / 参数里的数字转 int（容忍行尾注释、空值，失败回落默认值）"""
    try:
        return int(str(value).split("#")[0].strip())
    except (TypeError, ValueError):
        return default


def resolve_module(explicit, hint_text):
    """模块按项目分流：payroll → 393（结算/收款），假勤 → 392（考勤/假勤）

    重要：hint_text 只能包含**这一条**用例的信息（项目名 + 用例名 + 结果文件名）。
    传整批的名字会让一条假勤用例把整批单子都带到 392（历史 bug）。
    """
    payroll_module = _as_int(os.getenv("ZENTAO_MODULE_PAYROLL",
                                       os.getenv("ZENTAO_MODULE", "393")), 393)
    attendance_module = _as_int(os.getenv("ZENTAO_MODULE_ATTENDANCE", "392"), 392)
    if explicit:
        return _as_int(explicit, payroll_module), "命令行 --module"
    text = str(hint_text or "")
    if any(k in text for k in PAYROLL_KEYWORDS):
        return payroll_module, "本条用例关键词命中「薪资/结算/收款」"
    if any(k in text for k in ATTENDANCE_KEYWORDS):
        return attendance_module, "本条用例关键词命中「假勤」类"
    return payroll_module, "默认 payroll"


def resolve_sources(args):
    """返回 (files, hint_text)；结果过期且未 allow_stale 时返回 ([], hint)"""
    from core.last_run import print_record, read_last_run

    if args.source:
        return [args.source], ""

    record, age = read_last_run()
    if record:
        print_record(record, age)
        files = [f for f in (record.get("results") or []) if os.path.isfile(f)]
        # hint 只带项目名；用例名/结果文件名在逐条判定时各自补，避免整批串味
        hint = record.get("project") or ""
        if age > args.max_age_hours and not args.allow_stale:
            print("=" * 78)
            print("[结果过期] 本次执行结果是 %.1f 小时前的（保鲜期 %.0f 小时）"
                  % (age, args.max_age_hours))
            print("  → 想提单请先重跑：python run.py <api|ui> <项目名>")
            print("  → 确认要用旧结果：加 --allow-stale，或 --from <结果文件>")
            print("=" * 78)
            return [], hint
        if not files:
            print("[结果] 本次执行没有产生结果文件（可能全部跳过），改用文件时间取最新")
            return latest_result_files(), hint
        return files, hint

    files = [f for f in latest_result_files() if f]
    hint = ""
    if files:
        newest = max(os.path.getmtime(f) for f in files)
        age = (time.time() - newest) / 3600.0
        print("[提示] 没有 last_run.json（可能是旧版本执行的），按文件时间取最新：%.1f 小时前" % age)
        if age > args.max_age_hours and not args.allow_stale:
            print("[结果过期] 超过保鲜期 %.0f 小时，重跑或加 --allow-stale" % args.max_age_hours)
            return [], hint
    return files, hint


def main(argv=None):
    parser = argparse.ArgumentParser(description="执行结果 → 禅道提单（步骤/接口/截图齐全）")
    parser.add_argument("--probe", action="store_true", help="探测禅道连通性")
    parser.add_argument("--from", dest="source", default="", help="指定结果文件（默认取本次执行结果）")
    parser.add_argument("--module", type=int, default=0,
                        help="覆盖禅道模块 id（默认按项目分流：payroll=393 / 假勤=392）")
    parser.add_argument("--max-age-hours", type=float,
                        default=float(os.getenv("ZENTAO_RESULT_MAX_AGE_HOURS", "24")),
                        help="结果保鲜期（小时），默认 24")
    parser.add_argument("--allow-stale", action="store_true", help="结果过期也允许提单")
    parser.add_argument("--repeat", type=int, default=int(os.getenv("ZENTAO_REQUIRE_REPEAT", "2")),
                        help="稳定性要求：最近 N 天里至少有这么多「执行批次」失败过（默认 2）")
    parser.add_argument("--history-days", type=int, default=None,
                        help="历史失败统计窗口（天，0=不限）；默认读 ZENTAO_HISTORY_DAYS，否则 30")
    parser.add_argument("--include-env", action="store_true", help="同时提交环境类失败")
    parser.add_argument("--include-case", action="store_true", help="同时提交用例/数据类失败")
    parser.add_argument("--submit", action="store_true", help="真正提交（默认只出草稿）")
    parser.add_argument("--yes", action="store_true", help="确认提交（安全开关）")
    parser.add_argument("--delete-on-verify", action="store_true", help="提交后立即删除（自检用）")
    parser.add_argument("--severity", type=int, default=int(os.getenv("ZENTAO_SEVERITY", "3")))
    parser.add_argument("--pri", type=int, default=int(os.getenv("ZENTAO_PRI", "3")))
    parser.add_argument("--type", dest="bug_type", default=os.getenv("ZENTAO_TYPE", "codeerror"))
    args = parser.parse_args(argv)

    if args.probe:
        return probe()

    source_files, hint = resolve_sources(args)
    if not source_files:
        print("[结束] 没有可用的执行结果，未生成草稿")
        return 2
    failures, files = collect_failures(source_files)
    if not failures:
        print("没有找到失败用例（先跑一遍用例，或用 --from 指定结果文件）")
        return 0

    days = args.history_days if args.history_days is not None else history_days()
    history = history_failure_counts(days)
    print("[稳定性] 历史失败次数 = 最近%s出现过的执行批次数（同一批次内只算 1 次）"
          % ("（不限时间）" if days <= 0 else " %d 天" % days))
    allow = {"ASSERT"} | ({"ENV"} if args.include_env else set()) | ({"CASE"} if args.include_case else set())
    accepted, rejected = [], []
    for item in failures:
        item["class"] = classify(item["reason"])
        item["repeat"] = history.get((item["suite"], item["case_id"], item["name"]), 1)
        if item["class"] not in allow:
            rejected.append((item, f"非断言失败（{item['class']}）"))
        elif item["repeat"] < args.repeat:
            rejected.append((item, f"疑似偶发（历史失败 {item['repeat']} 次 < 要求 {args.repeat} 次）"))
        else:
            accepted.append(item)

    if rejected:
        print(f"按规则不提 {len(rejected)} 条：")
        for item, why in rejected[:10]:
            print(f"  - {item['case_id']} {item['name'][:30]} → {why}")
    if not accepted:
        print("\n没有符合「断言失败 + 稳定复现」的用例，不生成提单。")
        print("放宽：--repeat 1 / --include-env / --include-case")
        return 0

    auto = os.getenv("ZENTAO_AUTO_SUBMIT", "false").strip().lower() in ("true", "1", "yes", "y", "on")
    will_submit = args.submit and (args.yes or auto)
    if args.submit and not will_submit:
        print("[安全拦截] 未加 --yes，且 ZENTAO_AUTO_SUBMIT 不是 true → 只出草稿")

    print(f"\n准备提单 {len(accepted)} 条（每条都会带：步骤 / 接口请求返回 / 截图）\n")
    created_bugs = []
    for item in accepted:
        evidence = build_evidence(item)
        print("-" * 70)
        print(f"用例：{item['case_id']} {item['name']}")
        print(f"判定：{item['class']}｜历史失败 {item['repeat']} 次")
        calls = evidence.get("api_calls") or []
        keyword = evidence.get("api_keyword") or ""
        picked = [c for c in calls if keyword and keyword in (c.get("url") or "")] or calls[-1:]
        print(f"接口：{(picked[0].get('url') if picked else '（证据里没有接口记录）')}")
        print(f"截图：{'、'.join(os.path.basename(p) for p in evidence.get('screenshots') or []) or '（无）'}")
        if will_submit:
            # 逐条判定：只用这条用例自己的信息（项目名 + 用例名 + 结果文件名）
            hint_item = " ".join(x for x in (hint, str(item.get("name") or ""),
                                             str(item.get("source") or "")) if x)
            module, module_reason = resolve_module(args.module, hint_item)
            print(f"[模块] {module}（{module_reason}）")
            bug_id = evidence_bug.file_bug(evidence, submit=True, severity=args.severity,
                                          pri=args.pri, bug_type=args.bug_type, module=module)
            if bug_id:
                created_bugs.append(bug_id)
        else:
            md = evidence_bug.write_draft(evidence, evidence_bug.build_steps_html(evidence),
                                          evidence_bug.build_title(evidence))
            print(f"草稿：{md}")

    if args.delete_on_verify and created_bugs:
        from core.zentao import ZentaoClient
        client = ZentaoClient.from_env()
        client.login()
        for bug_id in created_bugs:
            try:
                client.delete_bug(bug_id)
                print(f"[自检] 已删除 #{bug_id}（--delete-on-verify）")
            except Exception as e:                       # noqa: BLE001
                print(f"[自检] 删除 #{bug_id} 失败：{e}")

    if not will_submit:
        print("\n未提交（草稿模式）。核对无误后：python run.py zentao --submit --yes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
