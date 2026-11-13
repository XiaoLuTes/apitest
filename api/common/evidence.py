"""接口用例证据采集

失败时产出两样东西（供禅道提单使用，格式与 UI 侧证据一致）：
    1. reports/evidence/api_<case>_<ts>.json   结构化证据（步骤 / 接口请求返回 / 断言明细）
    2. reports/screenshots/api_<case>_<ts>.png  "接口证据截图"（请求 + 返回 + 断言差异渲染成图）

为什么 API 也要截图：提单要求"每次都要有接口 + 对应截图"，
接口用例没有浏览器页面，就把请求/返回/断言渲染成图片，开发一眼能看懂。
"""
import json
import os
import re
import time

from core import paths

SHEET_LABEL = {
    "数据准备": "数据准备",
    "测试准备": "数据准备",
    "测试执行": "测试执行",
    "数据清理": "数据清理",
}


def _short(value, limit=1200):
    """把请求参数/响应体压成可读文本"""
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        try:
            text = json.dumps(value, ensure_ascii=False)
        except (TypeError, ValueError):
            text = str(value)
    else:
        text = str(value)
    text = text.strip()
    return text if len(text) <= limit else text[:limit] + f"...(截断,共{len(text)}字符)"


def _assert_digest(validate_result):
    """从断言结果里提取 期望/实际 明细"""
    expects, actuals = [], []
    for item in validate_result or []:
        if item.get("check_result"):
            continue
        key = item.get("key")
        expects.append(f"{key} 期望 {item.get('expected')}")
        actuals.append(f"{key} 实际 {item.get('actual')}")
    return expects, actuals


def build_api_evidence(file, req_info, validate_result, error):
    """组装接口侧证据包（字段与 ui/utils/evidence.py 的 EvidenceRecorder 输出一致）"""
    env = os.getenv("ENV", "测试环境")
    case_id = str(file.get("case_id") or "")
    name = str(file.get("name") or "")
    sheet = SHEET_LABEL.get(str(file.get("sheet") or ""), str(file.get("sheet") or ""))
    method = (req_info or {}).get("method") or str(file.get("method") or "")
    url = (req_info or {}).get("url") or ""
    expects, actuals = _assert_digest(validate_result)
    if not expects:
        # 断言失败时 assert_validata 直接抛异常，validate_result 拿不到，
        # 从错误文本里把「断言项 / 期望值 / 实际值」提出来
        pairs = re.findall(
            r"断言项\[(.+?)\]失败[^|]*\|\s*期望值[:：]\s*([^|]+?)\s*\|\s*实际值[:：]\s*([^|]+?)\s*(?:\||$)",
            str(error or ""))
        for path, expected, actual in pairs:
            expects.append(f"{path} 期望 {expected.strip()}")
            actuals.append(f"{path} 实际 {actual.strip()}")

    steps = [
        {"name": f"执行接口用例：{case_id} {name}", "action": "case",
         "note": f"用例文件：{os.path.basename(file.get('_file') or '')}（{sheet}）"},
        {"name": f"发送请求 {method} {url}".strip(), "action": "request",
         "data": _short((req_info or {}).get("request_body"), 300)},
        {"name": "按用例 validata 校验响应断言", "action": "assert"},
    ]

    api_calls = []
    if url:
        api_calls.append({
            "method": method,
            "url": url,
            "request_body": _short((req_info or {}).get("request_body"), 2000),
            "status": (req_info or {}).get("status"),
            "response": _short((req_info or {}).get("response"), 4000),
        })

    # 标题里带一句"现象"，方便一眼看懂（超长截断，禅道标题上限 255）
    brief = "；".join(expects[:2])
    title = f"{name}" if not brief else f"{name}"
    if brief:
        candidate = f"{name}：{brief}"
        title = candidate if len(candidate) <= 120 else f"{name}：{brief[:60]}"
    return {
        "title": title,
        "case_id": case_id,
        "env": env,
        "precondition": (f"接口自动化执行；环境：{env}；"
                         f"用例文件：{os.path.basename(file.get('_file') or '')}（{sheet}）"),
        "steps": steps,
        "api_calls": api_calls,
        "screenshots": [],
        "expect": "；".join(expects[:6]) or "与用例断言一致",
        "actual": "；".join(actuals[:6]) or str(error)[:600],
        "api_keyword": (req_info or {}).get("api_keyword") or "",
    }


# ============================================================================
# 把证据渲染成图片（接口用例没有页面，用一张"接口证据图"代替截图）
# ============================================================================

_FONT_CANDIDATES = (
    r"C:\Windows\Fonts\msyh.ttc",
    r"C:\Windows\Fonts\simhei.ttf",
    "/System/Library/Fonts/PingFang.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
)


def _load_font(size=14):
    from PIL import ImageFont
    for path in _FONT_CANDIDATES:
        if os.path.isfile(path):
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    return ImageFont.load_default()


def _wrap(text, font, max_width, draw):
    """按像素宽度折行（中文按字符切）"""
    lines = []
    for raw_line in str(text).splitlines() or [""]:
        line = ""
        for char in raw_line:
            if draw.textlength(line + char, font=font) <= max_width:
                line += char
            else:
                lines.append(line)
                line = char
        lines.append(line)
    return lines


def render_evidence_png(evidence, out_path=None, width=1100):
    """把证据渲染成一张 PNG：标题 + 步骤 + 接口请求 + 接口返回 + 断言差异"""
    from PIL import Image, ImageDraw

    os.makedirs(os.path.dirname(out_path or os.path.join(paths.SCREENSHOTS, "x.png")), exist_ok=True)
    if out_path is None:
        stamp = time.strftime("%Y%m%d_%H%M%S")
        safe = re.sub(r"[^\w\-]+", "_", str(evidence.get("case_id") or "api"))
        out_path = os.path.join(paths.SCREENSHOTS, f"api_{safe}_{stamp}.png")

    title_font = _load_font(18)
    body_font = _load_font(13)
    pad, line_gap = 16, 6
    max_width = width - pad * 2

    blocks = []
    blocks.append(("title", f"[自动化] {evidence.get('title') or ''}"))
    blocks.append(("meta", f"用例 {evidence.get('case_id')}｜环境 {evidence.get('env')}｜"
                           f"采集 {evidence.get('captured_at') or time.strftime('%Y-%m-%d %H:%M:%S')}"))
    blocks.append(("section", "[步骤]"))
    for idx, step in enumerate(evidence.get("steps") or [], start=1):
        text = f"{idx}. {step.get('name')}"
        if step.get("data"):
            text += f"    值：{step['data']}"
        blocks.append(("body", text))
    for call in (evidence.get("api_calls") or [])[:2]:
        blocks.append(("section", "[接口]"))
        blocks.append(("body", f"{call.get('method')} {call.get('url')}"))
        if call.get("status") is not None:
            blocks.append(("body", f"HTTP {call.get('status')}"))
        if call.get("request_body"):
            blocks.append(("section", "请求参数"))
            blocks.append(("mono", call.get("request_body")))
        if call.get("response"):
            blocks.append(("section", "接口返回"))
            blocks.append(("mono", call.get("response")))
    if evidence.get("expect"):
        blocks.append(("section", "[期望]"))
        blocks.append(("body", evidence.get("expect")))
    if evidence.get("actual"):
        blocks.append(("section", "[实际]"))
        blocks.append(("body", evidence.get("actual")))

    # 预排版：算出行与总高度
    probe = Image.new("RGB", (width, 10), "white")
    probe_draw = ImageDraw.Draw(probe)
    layout = []
    for kind, text in blocks:
        font = title_font if kind == "title" else body_font
        color = {"title": (20, 20, 20), "section": (0, 90, 160), "meta": (110, 110, 110)}.get(kind, (40, 40, 40))
        for line in _wrap(text, font, max_width, probe_draw):
            layout.append((kind, line, font, color))

    line_height = 20
    height = pad * 2 + len(layout) * line_height
    image = Image.new("RGB", (max(width, 400), max(height, 120)), "white")
    draw = ImageDraw.Draw(image)
    y = pad
    for kind, line, font, color in layout:
        if kind == "section":
            y += line_gap // 2
        draw.text((pad, y), line, font=font, fill=color)
        y += line_height
    image.save(out_path)
    return out_path


def save_api_evidence(file, req_info, validate_result, error):
    """落 JSON + 生成证据截图，返回 (json_path, png_path)"""
    evidence = build_api_evidence(file, req_info, validate_result, error)
    os.makedirs(os.path.join(paths.REPORTS, "evidence"), exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    safe = re.sub(r"[^\w\-]+", "_", f"{evidence['case_id']}_{evidence.get('title', '')[:20]}")
    json_path = os.path.join(paths.REPORTS, "evidence", f"api_{safe}_{stamp}.json")
    evidence["case_ref"] = {"file": os.path.basename(file.get("_file") or ""), "case_id": evidence["case_id"],
                            "name": evidence["title"]}
    try:
        png_path = render_evidence_png(evidence, out_path=os.path.join(
            paths.SCREENSHOTS, f"api_{safe}_{stamp}.png"))
        evidence["screenshots"] = [png_path]
    except Exception:                             # noqa: BLE001
        png_path = None
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(evidence, f, ensure_ascii=False, indent=2)
    return json_path, png_path
