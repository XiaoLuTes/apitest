#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""执行结果 → 禅道提单（默认只出草稿，--submit 才真提）

模板已对齐公司禅道（开源版 22.6，http://172.21.100.100:8101/zentao）：
    所属产品 = GSR OMNI(1)      所属模块 = /Payroll&结算(393)
    严重程度 = 3(一般)          优先级 = 3(中)        类型 = codeerror(代码错误)
    影响版本 = ["trunk"]（主干） 反馈者 = 登录账号      当前指派 = ZENTAO_ASSIGNEE
    重现步骤 = HTML 富文本，[前置条件]/[步骤]/[结果]/[期望]/[备注]
    标题      = 【自动化-<环境>】<用例名>：<现象摘要>

用法：
    python run.py zentao --probe                        # 探测连通性/身份/产品
    python run.py zentao                                # 最近一次结果 → 草稿
    python run.py zentao --from reports/results/api/x.xlsx
    python run.py zentao --submit --yes                 # 真提交（草稿核对后）
    python run.py zentao --submit --yes --delete-on-verify   # 验证用：提交后立刻删除

已知限制（实测）：
    附件走 REST 上传被服务端拒（png/xlsx/txt 都报"文件格式不在规定范围内"），
    因此模板把结果文件路径写进 [备注]，需要贴图时人工补或改用 UI 方式提单。
"""
import argparse
import glob
import json
import os
import re
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from core import paths  # noqa: E402
from core.env import load_env  # noqa: E402

load_env()

DRAFT_DIR = os.path.join(paths.REPORTS, "zentao")
DEFAULT_KEYWORDS = "自动化"


# ============================================================================
# 1. 读执行结果，收集失败用例
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
                case_id = row[idx["case_id"]] if "case_id" in idx and idx["case_id"] < len(row) else ""
                name = row[idx["name"]] if "name" in idx and idx["name"] < len(row) else ""
                failures.append({
                    "suite": "api",
                    "source": os.path.basename(xlsx_path),
                    "sheet": sheet,
                    "case_id": "" if case_id is None else str(case_id),
                    "name": "" if name is None else str(name),
                    "reason": result.replace("失败：", "").replace("失败:", "").strip(),
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
            "reason": result.replace("失败：", "").replace("失败:", "").strip(),
        })
    return failures


def latest_result_files():
    api = sorted(glob.glob(os.path.join(paths.RESULTS_API, "*.xlsx")), key=os.path.getmtime)
    ui = sorted(glob.glob(os.path.join(paths.RESULTS_UI, "*.yaml")), key=os.path.getmtime)
    return (api[-1] if api else None), (ui[-1] if ui else None)


def collect_failures(source=None):
    files = [source] if source else [f for f in latest_result_files() if f]
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
# 2. 聚类（同根因合成一条缺陷）
# ============================================================================


def fingerprint(reason):
    text = str(reason or "")
    text = re.sub(r"\b[0-9a-f]{8,}\b", "<id>", text, flags=re.I)
    text = re.sub(r"\d+", "<n>", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:120] or "未知原因"


def cluster(failures):
    groups = {}
    for item in failures:
        groups.setdefault(fingerprint(item["reason"]), []).append(item)
    clusters = [{"fingerprint": fp, "items": items} for fp, items in groups.items()]
    clusters.sort(key=lambda c: -len(c["items"]))
    return clusters


# ============================================================================
# 3. 按公司禅道模板生成草稿
# ============================================================================


def _esc(text):
    return (str(text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def _plain(text):
    return re.sub(r"\s+", " ", str(text or "")).strip()


def build_title(item, env_name):
    """标题风格对齐公司禅道：【来源】模块-页面：单据号/对象，现象"""
    name = _plain(item.get("name") or item.get("case_id"))
    reason = _plain(item.get("reason"))
    matched = re.search(r"(断言项\[[^\]]+\]失败[^；;]{0,60})", reason)
    brief = matched.group(1) if matched else reason
    return f"【自动化-{env_name}】{name}：{brief[:80]}"


def build_steps_html(item, items, files, env_name):
    """重现步骤：公司模板 [前置条件]/[步骤]/[结果]/[期望]/[备注]（HTML）"""
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    reason_lines = [line for line in str(item["reason"]).splitlines() if line.strip()]
    reason_html = "<br/>".join(_esc(line) for line in reason_lines) or "（无错误详情）"
    # [期望] 只取「期望值」，不要把整行错误重复一遍
    expects = []
    for line in reason_lines:
        matched = re.search(r"断言项\[([^\]]+)\][^|]*\|?\s*期望值:\s*([^|]+)", line)
        if matched:
            expects.append(f"{matched.group(1).strip()} 期望 {matched.group(2).strip()}")
        elif "期望" in line:
            expects.append(_plain(line)[:200])
    expect_html = "<br/>".join(_esc(item) for item in expects[:10]) \
        or "与用例断言一致（详见用例与结果文件）"
    merged = "、".join(f"{i['case_id']} {i['name']}" for i in items[:10])

    return "".join([
        "<p><strong>[前置条件]</strong></p>",
        f"<p>自动化用例稳定复现，无需人工准备数据；执行环境：{_esc(env_name)}</p>",
        "<p><strong>[步骤]</strong></p>",
        f"<p>1. 执行用例：{_esc(item['case_id'])} {_esc(item['name'])}</p>",
        f"<p>2. 用例文件：{_esc(item['source'])}（{_esc(item.get('sheet') or item['suite'])}）</p>",
        f"<p>3. 执行时间：{ts}</p>",
        "<p><strong>[结果]</strong></p>",
        f"<p>{reason_html}</p>",
        "<p><strong>[期望]</strong></p>",
        f"<p>{expect_html}</p>",
        "<p><strong>[备注]</strong></p>",
        f"<p>同根因用例 {len(items)} 条：{_esc(merged)}</p>",
        f"<p>结果文件：{_esc('; '.join(os.path.basename(f) for f in files))}"
        f"（reports/results/ 下可查；API 附件上传被禅道限制，如需截图请人工补传）</p>",
    ])


def build_draft(clusters, env_name, product, module, assignee, severity, pri, bug_type, files,
                opened_build="trunk", feedback_by="", keywords=DEFAULT_KEYWORDS):
    drafts = []
    for index, cluster in enumerate(clusters, start=1):
        items = cluster["items"]
        first = items[0]
        drafts.append({
            "序号": index,
            "标题": build_title(first, env_name),
            "产品": product,
            "模块": module,
            "严重程度": severity,
            "优先级": pri,
            "类型": bug_type,
            "指派给": assignee,
            "影响版本": opened_build,
            "反馈者": feedback_by,
            "关键词": keywords,
            "影响用例数": len(items),
            "涉及用例": "、".join(f"{i['case_id']}{i['name']}" for i in items[:3])
                        + ("…" if len(items) > 3 else ""),
            "重现步骤": build_steps_html(first, items, files, env_name),
            "错误指纹": cluster["fingerprint"],
        })
    return drafts


def write_draft(drafts):
    os.makedirs(DRAFT_DIR, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    md_path = os.path.join(DRAFT_DIR, f"draft_{stamp}.md")
    xlsx_path = os.path.join(DRAFT_DIR, f"draft_{stamp}.xlsx")

    lines = [f"# 禅道提单草稿（{stamp}）", "", f"共 {len(drafts)} 条（已按错误指纹聚合同根因）", ""]
    for d in drafts:
        lines += [
            f"## {d['序号']}. {d['标题']}",
            "",
            f"- 产品：{d['产品']}　模块：{d['模块']}　严重程度：{d['严重程度']}　"
            f"优先级：{d['优先级']}　类型：{d['类型']}",
            f"- 影响版本：{d['影响版本']}　反馈者：{d['反馈者'] or '（登录账号）'}　"
            f"指派给：{d['指派给'] or '（默认）'}　关键词：{d['关键词']}",
            f"- 影响用例数：{d['影响用例数']}　涉及用例：{d['涉及用例']}",
            "",
            "**重现步骤（提交时转成 HTML）**",
            "",
            "```html",
            d["重现步骤"],
            "```",
            "",
        ]
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "提单草稿"
    headers = ["序号", "标题", "产品", "模块", "严重程度", "优先级", "类型", "指派给",
               "影响版本", "反馈者", "关键词", "影响用例数", "涉及用例", "重现步骤", "错误指纹"]
    ws.append(headers)
    for d in drafts:
        ws.append([d[h] for h in headers])
    for idx, width in enumerate([6, 60, 8, 8, 10, 8, 12, 12, 10, 12, 12, 10, 40, 80, 40], start=1):
        ws.column_dimensions[openpyxl.utils.get_column_letter(idx)].width = width
    wb.save(xlsx_path)
    wb.close()
    return md_path, xlsx_path


# ============================================================================
# 4. 探测禅道
# ============================================================================


def probe():
    from core.zentao import ZentaoClient, ZentaoError

    print("=" * 70)
    try:
        client = ZentaoClient.from_env()
    except ZentaoError as e:
        print(e)
        print("\n配置位置：.env（参考 .env.example 的 ZENTAO_* 段）")
        return 2

    print(f"禅道地址：{client.url}")
    print(f"鉴权方式：{'token（.env 直给）' if client.token else '账号密码换 token'}")
    try:
        client.login()
        print(f"登录结果：成功（mode={client.mode}）")
    except ZentaoError as e:
        print(f"登录结果：失败 → {e}")
        return 2

    for label, func in (("当前用户 /api.php/v1/user", client.whoami),
                        ("产品列表 /api.php/v1/products", client.products),
                        ("用户列表 /api.php/v1/users", client.users)):
        try:
            data = func()
            if isinstance(data, dict):
                data = data.get("profile") or data.get("user") or data
            sample = data[:3] if isinstance(data, list) else data
            print(f"{label}：可用 → {json.dumps(sample, ensure_ascii=False)[:260]}")
        except ZentaoError as e:
            print(f"{label}：不可用 → {e}")

    product = os.getenv("ZENTAO_PRODUCT", "").strip()
    if product:
        try:
            mods = client.modules(product)
            print(f"模块列表（产品 {product}）：{mods if mods else '该版本无模块 REST 端点，模块 id 从提单页 URL 取'}")
        except ZentaoError as e:
            print(f"模块列表（产品 {product}）：不可用 → {e}")
    print("\n提单默认值：产品 {} / 模块 {} / 严重程度 {} / 优先级 {} / 类型 {} / 影响版本 {}".format(
        os.getenv("ZENTAO_PRODUCT", "1"), os.getenv("ZENTAO_MODULE", "393"),
        os.getenv("ZENTAO_SEVERITY", "3"), os.getenv("ZENTAO_PRI", "3"),
        os.getenv("ZENTAO_TYPE", "codeerror"), os.getenv("ZENTAO_OPENED_BUILD", "trunk")))
    print("提示：先不带 --submit 出草稿核对，再 --submit --yes 提交")
    return 0


# ============================================================================
# 5. 提交
# ============================================================================


def submit(drafts, args, files):
    from core.zentao import ZentaoClient, ZentaoError

    auto = os.getenv("ZENTAO_AUTO_SUBMIT", "false").strip().lower() in ("true", "1", "yes", "y", "on")
    if not (args.yes or auto):
        print("[安全拦截] 未加 --yes，且 .env 的 ZENTAO_AUTO_SUBMIT 不是 true → 只生成草稿，不提交")
        return 0

    try:
        client = ZentaoClient.from_env()
        client.login()
    except ZentaoError as e:
        print(f"[提单失败] {e}")
        return 2

    submitted = 0
    created = []
    for d in drafts:
        try:
            bug_id = client.create_bug(
                title=d["标题"], steps=d["重现步骤"],
                product=args.product, module=args.module,
                severity=args.severity, pri=args.pri, bug_type=args.bug_type,
                assigned_to=args.assignee, feedback_by=args.feedback_by,
                opened_build=args.opened_build, keywords=args.keywords,
            )
            submitted += 1
            print(f"[已提交] #{bug_id} {d['标题']}")
            print(f"          {client.url}/bug-view-{bug_id}.html")
            if args.delete_on_verify:
                try:
                    view = client.request("GET", f"/api.php/v1/bugs/{bug_id}")
                    print("          [回读字段] " + json.dumps({
                        k: view.get(k) for k in ("module", "severity", "pri", "type",
                                                  "keywords", "openedBuild", "assignedTo")
                    }, ensure_ascii=False))
                    client.delete_bug(bug_id)
                    print(f"          [验证模式] 已删除 #{bug_id}")
                except ZentaoError as e:
                    print(f"          回读/删除失败：{e}")
                    created.append(bug_id)
            else:
                created.append(bug_id)
        except ZentaoError as e:
            print(f"[提交失败] {d['标题']} → {e}")
    print(f"\n提交完成：成功 {submitted} / 共 {len(drafts)}")
    return 0 if submitted == len(drafts) else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description="执行结果 → 禅道提单（默认只生成草稿）")
    parser.add_argument("--probe", action="store_true", help="探测禅道连通性/接口形态")
    parser.add_argument("--from", dest="source", default="", help="指定结果文件（默认取最新）")
    parser.add_argument("--product", default=os.getenv("ZENTAO_PRODUCT", "1"), help="所属产品 id")
    parser.add_argument("--module", default=os.getenv("ZENTAO_MODULE", "393"), help="所属模块 id")
    parser.add_argument("--assignee", default=os.getenv("ZENTAO_ASSIGNEE", ""), help="当前指派（账号名）")
    parser.add_argument("--feedback-by", default=os.getenv("ZENTAO_FEEDBACK", ""),
                        help="反馈者（默认登录账号）")
    parser.add_argument("--severity", type=int, default=int(os.getenv("ZENTAO_SEVERITY", "3")),
                        help="严重程度 1~4（3=一般）")
    parser.add_argument("--pri", type=int, default=int(os.getenv("ZENTAO_PRI", "3")),
                        help="优先级 1~4（3=中）")
    parser.add_argument("--type", dest="bug_type", default=os.getenv("ZENTAO_TYPE", "codeerror"),
                        help="类型：codeerror/codeimprovement/others...")
    parser.add_argument("--opened-build", default=os.getenv("ZENTAO_OPENED_BUILD", "trunk"),
                        help="影响版本：trunk=主干（默认），也可传 build id")
    parser.add_argument("--keywords", default=os.getenv("ZENTAO_KEYWORDS", DEFAULT_KEYWORDS),
                        help="关键词（默认 自动化）")
    parser.add_argument("--submit", action="store_true", help="真正提交到禅道（默认只出草稿）")
    parser.add_argument("--yes", action="store_true", help="确认提交（安全开关）")
    parser.add_argument("--delete-on-verify", action="store_true",
                        help="验证用：提交成功后立即删除该单")
    args = parser.parse_args(argv)

    if args.probe:
        return probe()

    failures, files = collect_failures(args.source or None)
    if not failures:
        print("没有找到失败用例（先跑一遍用例，或用 --from 指定结果文件）")
        return 0

    env_name = os.getenv("ENV", "测试环境")
    clusters = cluster(failures)
    drafts = build_draft(clusters, env_name, args.product, args.module, args.assignee,
                         args.severity, args.pri, args.bug_type, files,
                         opened_build=args.opened_build, feedback_by=args.feedback_by,
                         keywords=args.keywords)
    md_path, xlsx_path = write_draft(drafts)
    print(f"失败用例 {len(failures)} 条，按根因聚合成 {len(drafts)} 条缺陷草稿")
    print(f"  Markdown：{md_path}")
    print(f"  Excel   ：{xlsx_path}")
    if args.submit:
        return submit(drafts, args, files)
    print("未提交（默认只出草稿）。核对无误后：python run.py zentao --submit --yes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
