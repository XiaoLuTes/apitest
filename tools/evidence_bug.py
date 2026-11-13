#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""证据包 → 禅道缺陷单（步骤 / 接口返回 / 页面截图 全带上）

流程：
    1. REST 建单（字段可靠：产品/模块/严重程度/优先级/类型/指派/影响版本）
    2. 浏览器补传截图（REST 附件接口被服务端限制，页面表单正常）
    3. 回读附件 id，把截图内联进「重现步骤」（<img src="{文件id.png}">，与公司存量单一致）

证据包来源：ui/utils/evidence.py 的 EvidenceRecorder，或手写 JSON。字段：
    {
      "title": "按薪资包ID搜索返回值不存在的关键字",
      "case_id": "PKG-SEARCH-01",
      "env": "测试环境",
      "precondition": "…",            # 可选
      "expect": "…",                  # 必填：期望结果（人话，不要写断言原文）
      "actual": "…",                  # 可选：实际现象（默认从接口返回推断）
      "steps": [{"name": "...", "action": "input", "element": "...", "data": "..."}],
      "api_calls": [{"method": "GET", "url": "...", "status": 200, "response": "{...}"}],
      "screenshots": ["reports/screenshots/xxx.png"]
    }

用法：
    python tools/evidence_bug.py --evidence reports/evidence/xxx.json            # 只出草稿
    python tools/evidence_bug.py --evidence reports/evidence/xxx.json --submit   # 真提单
"""
import argparse
import html
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


def _esc(text):
    return html.escape(str(text or ""), quote=False)


def _brief_response(call, limit=600):
    """把接口返回压成一行可读摘要（保留关键字段）"""
    body = (call or {}).get("response") or ""
    try:
        data = json.loads(body)
        if isinstance(data, dict):
            keep = {k: data[k] for k in
                    ("code", "msg", "total", "status", "error", "data", "rows") if k in data}
            if isinstance(keep.get("rows"), list):
                keep["rows"] = f"<{len(keep['rows'])} 条>"
            body = json.dumps(keep, ensure_ascii=False)
            if len(body) > limit:                 # data 太长时保留关键结构
                if isinstance(keep.get("data"), dict):
                    keep["data"] = {k: keep["data"][k] for k in list(keep["data"])[:12]}
                body = json.dumps(keep, ensure_ascii=False)
    except ValueError:
        # 响应被截断导致 JSON 不完整时，尽量抽出 total/rows 的规模
        matched_total = re.search(r'"total"\s*:\s*(\d+)', body)
        matched_code = re.search(r'"code"\s*:\s*(\d+)', body)
        snippet = []
        if matched_code:
            snippet.append(f'"code": {matched_code.group(1)}')
        if matched_total:
            snippet.append(f'"total": {matched_total.group(1)}')
        snippet.append(f'"rows": <{"空" if matched_total and matched_total.group(1) == "0" else "见原始响应"}>')
        body = "{" + ", ".join(snippet) + "}"
    return body[:limit]


def _pre(text):
    """等宽块：禅道富文本里用 pre 保持 JSON 缩进/换行"""
    return ('<pre style="font-family:Consolas,Monaco,monospace;font-size:12px;'
            'background:#f6f8fa;padding:8px;border-radius:4px;white-space:pre-wrap;'
            f'word-break:break-all;">{_esc(text)}</pre>')


def build_steps_html(evidence, image_ids=None):
    """按"接口证据图"的结构生成重现步骤：

        [前置条件] / [步骤] / [接口] / [请求参数] / [接口返回] / [期望] / [实际] / [截图] / [备注]

    - 接口类：接口 / 请求参数 / 接口返回 三段齐全（不配截图）
    - UI 类：步骤 + 接口（页面抓到的请求）+ 期望/实际 + 截图
    """
    steps = evidence.get("steps") or []
    api_calls = evidence.get("api_calls") or []
    env = evidence.get("env") or os.getenv("ENV", "测试环境")
    parts = ["<p><strong>[前置条件]</strong></p>",
             f"<p>{_esc(evidence.get('precondition') or f'管理端已登录；环境：{env}')}</p>"]

    # ---- [步骤] ----
    parts.append("<p><strong>[步骤]</strong></p>")
    for idx, step in enumerate(steps, start=1):
        detail = step.get("name") or ""
        if step.get("data"):
            detail += f"（值：{step['data']}）"
        if step.get("note"):
            detail += f"（{step['note']}）"
        parts.append(f"<p>{idx}. {_esc(detail)}</p>")

    # ---- [接口] / [请求参数] / [接口返回] ----
    keyword = evidence.get("api_keyword") or ""
    picked = [c for c in api_calls if keyword and keyword in (c.get("url") or "")]
    call = (picked[-1:] or api_calls[-1:])
    call = call[0] if call else None
    if call:
        status = call.get("status")
        status_text = f"（HTTP {status}）" if status is not None else ""
        parts.append("<p><strong>[接口]</strong></p>")
        parts.append(f"<p>{_esc(call.get('method'))} {_esc(call.get('url'))}{status_text}</p>")
        if call.get("request_body"):
            parts.append("<p><strong>[请求参数]</strong></p>")
            parts.append(_pre(call.get("request_body")))
        if call.get("response"):
            parts.append("<p><strong>[接口返回]</strong></p>")
            parts.append(_pre(_brief_response(call)))

    # ---- [期望] / [实际] ----
    parts.append("<p><strong>[期望]</strong></p>")
    parts.append(f"<p>{_esc(evidence.get('expect') or '（需补充期望结果）')}</p>")
    if evidence.get("actual"):
        parts.append("<p><strong>[实际]</strong></p>")
        parts.append(f"<p>{_esc(evidence.get('actual'))}</p>")

    # ---- [截图]：只有真有图（UI 失败）才写 ----
    shots = [os.path.basename(p) for p in (evidence.get("screenshots") or []) if os.path.isfile(p)]
    if shots:
        parts.append("<p><strong>[截图]</strong></p>")
        parts.append("<p>见本单附件：" + "、".join(_esc(name) for name in shots) + "</p>")

    # ---- [备注] ----
    parts.append("<p><strong>[备注]</strong></p>")
    parts.append(f"<p>自动化提单：用例 {_esc(evidence.get('case_id'))}，"
                 f"采集时间 {_esc(evidence.get('captured_at') or time.strftime('%Y-%m-%d %H:%M:%S'))}；"
                 f"页面地址 {_esc(evidence.get('url'))}</p>")
    return "".join(parts)


def build_title(evidence, env_name=None):
    env_name = env_name or evidence.get("env") or os.getenv("ENV", "测试环境")
    title = evidence.get("title") or evidence.get("case_id") or "自动化发现的问题"
    return f"【自动化-{env_name}】{title}"


def write_draft(evidence, steps_html, title):
    os.makedirs(DRAFT_DIR, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    md = os.path.join(DRAFT_DIR, f"evidence_draft_{stamp}.md")
    with open(md, "w", encoding="utf-8") as f:
        f.write(f"# {title}\n\n")
        f.write(f"- 用例：{evidence.get('case_id')}\n- 环境：{evidence.get('env')}\n")
        f.write(f"- 截图：{len(evidence.get('screenshots') or [])} 张\n\n")
        f.write("## 重现步骤（提交时转 HTML）\n\n```html\n")
        f.write(steps_html)
        f.write("\n```\n")
    return md


def file_bug(evidence, submit=False, severity=3, pri=3, bug_type="codeerror", module=None):
    from core.zentao import ZentaoClient, ZentaoError

    title = build_title(evidence)
    steps_html = build_steps_html(evidence)
    md = write_draft(evidence, steps_html, title)
    print(f"标题：{title}")
    print(f"草稿：{md}")
    print(f"步骤数：{len(evidence.get('steps') or [])}｜接口记录：{len(evidence.get('api_calls') or [])}"
          f"｜截图：{len(evidence.get('screenshots') or [])}")
    if not submit:
        print("\n只生成草稿。确认后加 --submit 真提单。")
        return None

    try:
        client = ZentaoClient.from_env()
        client.login()
        bug_id = client.create_bug(
            title=title, steps=steps_html, product=int(os.getenv("ZENTAO_PRODUCT", "1")),
            module=int(module or os.getenv("ZENTAO_MODULE", "393")), severity=severity, pri=pri,
            bug_type=bug_type, assigned_to=os.getenv("ZENTAO_ASSIGNEE", ""),
            feedback_by=os.getenv("ZENTAO_FEEDBACK", "") or client.account,
            opened_build=os.getenv("ZENTAO_OPENED_BUILD", "trunk"),
            keywords=os.getenv("ZENTAO_KEYWORDS", "自动化"))
        print(f"\n[已建单] #{bug_id} {client.url}/bug-view-{bug_id}.html")
    except ZentaoError as e:
        print(f"\n[建单失败] {e}")
        return None

    attach_and_inline(bug_id, evidence, client)
    print(f"\n完成：{client.url}/bug-view-{bug_id}.html")
    return bug_id


def attach_and_inline(bug_id, evidence, client=None):
    """给已存在的缺陷补传截图，并把图片内联进重现步骤"""
    from core.zentao import ZentaoClient

    client = client or ZentaoClient.from_env()
    client.login()
    shots = [p for p in (evidence.get("screenshots") or []) if os.path.isfile(p)]
    if not shots:
        print("[附件] 证据里没有截图，跳过")
        return []
    try:
        # 去重：同名附件已经在这个单上就不再重复上传
        current = client.request("GET", f"/api.php/v1/bugs/{bug_id}").get("files") or {}
        existing = {str(meta.get("title") or "") for meta in current.values()}
        shots = [p for p in shots if os.path.basename(p) not in existing]
        if not shots:
            print("[附件] 同名截图已在单据上，跳过重复上传")
            client.update_bug(bug_id, steps=build_steps_html(evidence))
            return list(current.keys())

        from core.zentao_ui import upload_attachments
        upload_attachments(bug_id, shots, client.url, client.account, client.password, headless=True)
        detail = client.request("GET", f"/api.php/v1/bugs/{bug_id}")
        files = detail.get("files") or {}
        image_ids = [fid for fid, meta in files.items()
                     if str(meta.get("extension", "")).lower() in ("png", "jpg", "jpeg", "gif")]
        # 附件已经是图片了，步骤里只需要引用附件名（占位符 <img> 在该版本不渲染）
        client.update_bug(bug_id, steps=build_steps_html(evidence))
        if image_ids:
            print(f"[已上传截图] {len(image_ids)} 张附件，步骤已注明附件名")
        return image_ids
    except Exception as e:                       # noqa: BLE001
        print(f"[附件处理失败] {e}")
        return []


def main(argv=None):
    parser = argparse.ArgumentParser(description="证据包 → 禅道缺陷单")
    parser.add_argument("--evidence", required=True, help="证据 JSON 路径")
    parser.add_argument("--submit", action="store_true", help="真的提单（默认只出草稿）")
    parser.add_argument("--attach-to", type=int, default=0,
                        help="不新建单，只给已存在的缺陷补附件并内联截图")
    parser.add_argument("--severity", type=int, default=int(os.getenv("ZENTAO_SEVERITY", "3")))
    parser.add_argument("--pri", type=int, default=int(os.getenv("ZENTAO_PRI", "3")))
    parser.add_argument("--type", dest="bug_type", default=os.getenv("ZENTAO_TYPE", "codeerror"))
    args = parser.parse_args(argv)

    with open(args.evidence, "r", encoding="utf-8") as f:
        evidence = json.load(f)
    evidence.setdefault("env", os.getenv("ENV", "测试环境"))
    if args.attach_to:
        attach_and_inline(args.attach_to, evidence)
        return 0
    file_bug(evidence, submit=args.submit, severity=args.severity, pri=args.pri,
             bug_type=args.bug_type)
    return 0


if __name__ == "__main__":
    sys.exit(main())
