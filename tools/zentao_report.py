#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""执行结果 → 禅道提单（草稿默认，--submit 才真提）

用法：
    python run.py zentao --probe                          # 探测禅道连通性/接口形态/产品模块账号
    python run.py zentao                                  # 从最近一次执行结果生成提单草稿（不提交）
    python run.py zentao --from reports/results/api/xxx.xlsx
    python run.py zentao --product 3 --module 12          # 指定产品/模块（否则取 .env）
    python run.py zentao --submit --yes                   # 真正提交（需要 .env 配置齐全）

产出：
    reports/zentao/draft_<时间戳>.md      人看的草稿（标题/原因/复现步骤/建议字段）
    reports/zentao/draft_<时间戳>.xlsx    可直接核对字段的表格

设计原则：
    1. 默认只生成草稿，绝不自动提单（避免把环境问题刷进缺陷库）
    2. 相同"错误指纹"的失败聚合成一条缺陷，避免一条根因报 N 个 bug
    3. 每条草稿都带执行环境、用例ID、原始错误文本、结果文件路径，方便开发定位
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


# ============================================================================
# 1. 读执行结果，收集失败用例
# ============================================================================


def _read_api_failures(xlsx_path):
    """从接口结果文件（源用例副本 + result 列）里取失败用例"""
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
                    "reason": result.replace("失败：", "").strip(),
                })
    finally:
        wb.close()
    return failures


def _read_ui_failures(yaml_path):
    """从 UI 结果文件（test_cases[].result）里取失败用例"""
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
        })
    return failures


def latest_result_files():
    """找最近一次执行的接口/UI 结果文件"""
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
    """错误指纹：抹掉数字、id、时间戳等易变内容，保留稳定特征"""
    text = str(reason or "")
    text = re.sub(r"\b[0-9a-f]{8,}\b", "<id>", text, flags=re.I)
    text = re.sub(r"\d+", "<n>", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:120] or "未知原因"


def cluster(failures):
    groups = {}
    for item in failures:
        groups.setdefault(fingerprint(item["reason"]), []).append(item)
    clusters = []
    for fp, items in groups.items():
        clusters.append({"fingerprint": fp, "items": items})
    clusters.sort(key=lambda c: -len(c["items"]))
    return clusters


# ============================================================================
# 3. 生成草稿
# ============================================================================


def build_draft(clusters, env_name, product, module, assignee, severity, pri, bug_type, files):
    drafts = []
    for index, cluster in enumerate(clusters, start=1):
        items = cluster["items"]
        first = items[0]
        titles = "、".join(f"{i['case_id']}{i['name']}" for i in items[:3])
        short_reason = re.sub(r"\s+", " ", first["reason"])[:80]
        draft = {
            "序号": index,
            "标题": f"[自动化][{env_name}] {first['name'] or first['case_id']} 失败：{short_reason}",
            "产品": product,
            "模块": module,
            "严重程度": severity,
            "优先级": pri,
            "类型": bug_type,
            "指派给": assignee,
            "影响用例数": len(items),
            "涉及用例": titles + ("…" if len(items) > 3 else ""),
            "重现步骤": (
                f"【执行环境】{env_name}\n"
                f"【用例集】{first['source']}（{first['sheet'] or first['suite']}）\n"
                f"【失败用例】\n" + "\n".join(
                    f"  - {i['case_id']} {i['name']}" for i in items[:10]) + "\n"
                f"【错误信息】\n{first['reason']}\n"
                f"【结果文件】{'; '.join(os.path.basename(f) for f in files)}\n"
                f"【备注】同根因用例已合并，共 {len(items)} 条"
            ),
            "错误指纹": cluster["fingerprint"],
        }
        drafts.append(draft)
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
            f"- 产品：{d['产品']}　模块：{d['模块']}　严重程度：{d['严重程度']}　优先级：{d['优先级']}　类型：{d['类型']}",
            f"- 指派给：{d['指派给'] or '（默认）'}　影响用例数：{d['影响用例数']}",
            f"- 涉及用例：{d['涉及用例']}",
            "",
            "```",
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
               "影响用例数", "涉及用例", "重现步骤", "错误指纹"]
    ws.append(headers)
    for d in drafts:
        ws.append([d[h] for h in headers])
    for idx, width in enumerate([6, 60, 8, 8, 10, 8, 12, 12, 10, 50, 80, 40], start=1):
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
        print("\n排查建议：1) 地址是否带 /api.php 2) 版本是否 ≥18 3) 账号是否有 API 权限")
        return 2

    for label, func in (("当前用户 /api.php/v1/user", client.whoami),
                        ("产品列表 /api.php/v1/products", client.products),
                        ("用户列表 /api.php/v1/users", client.users)):
        try:
            data = func()
            if isinstance(data, dict):
                data = data.get("profile") or data.get("user") or data
            sample = data[:3] if isinstance(data, list) else data
            print(f"{label}：可用 → {json.dumps(sample, ensure_ascii=False)[:300]}")
        except ZentaoError as e:
            print(f"{label}：不可用 → {e}")

    product = os.getenv("ZENTAO_PRODUCT", "").strip()
    if product:
        try:
            print(f"模块列表（产品 {product}）：可用 → "
                  f"{json.dumps(client.modules(product), ensure_ascii=False)[:300]}")
        except ZentaoError as e:
            print(f"模块列表（产品 {product}）：不可用 → {e}")
    else:
        print("模块列表：跳过（未配置 ZENTAO_PRODUCT）")

    print("\n提示：提单前建议先用默认草稿模式核对字段，确认无误再加 --submit --yes")
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

    created = []
    for d in drafts:
        try:
            bug_id = client.create_bug(
                title=d["标题"], steps=d["重现步骤"],
                product=args.product, module=args.module,
                severity=args.severity, pri=args.pri, bug_type=args.bug_type,
                assigned_to=args.assignee, attachments=files,
            )
            created.append((bug_id, d["标题"]))
            print(f"[已提交] #{bug_id} {d['标题']}")
        except ZentaoError as e:
            print(f"[提交失败] {d['标题']} → {e}")
    print(f"\n提交完成：成功 {len(created)} / 共 {len(drafts)}")
    return 0 if len(created) == len(drafts) else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description="执行结果 → 禅道提单（默认只生成草稿）")
    parser.add_argument("--probe", action="store_true", help="探测禅道连通性/接口形态")
    parser.add_argument("--from", dest="source", default="", help="指定结果文件（默认取最新）")
    parser.add_argument("--product", default=os.getenv("ZENTAO_PRODUCT", "0"), help="产品 id")
    parser.add_argument("--module", default=os.getenv("ZENTAO_MODULE", "0"), help="模块 id")
    parser.add_argument("--assignee", default=os.getenv("ZENTAO_ASSIGNEE", ""), help="指派给（账号名）")
    parser.add_argument("--severity", type=int, default=int(os.getenv("ZENTAO_SEVERITY", "3")),
                        help="严重程度 1~4（1 最严重）")
    parser.add_argument("--pri", type=int, default=int(os.getenv("ZENTAO_PRI", "3")),
                        help="优先级 1~4（1 最高）")
    parser.add_argument("--type", dest="bug_type", default=os.getenv("ZENTAO_TYPE", "codeerror"),
                        help="缺陷类型：codeerror/performance/standard/automation/others...")
    parser.add_argument("--submit", action="store_true", help="真正提交到禅道（默认只出草稿）")
    parser.add_argument("--yes", action="store_true", help="确认提交（安全开关）")
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
                         args.severity, args.pri, args.bug_type, files)
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
