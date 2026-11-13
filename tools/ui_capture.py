# -*- coding: utf-8 -*-
"""现场采集：登录（需要时人工扫码）→ 按菜单路径导航 → 导出候选定位器

用法：
    python tools/ui_capture.py --menu "Payroll/算薪/薪资包管理" --out reports/_probe
    python tools/ui_capture.py --url https://test-admin.gsrtech.com/payrollSalaryPackage
    python tools/ui_capture.py --menu "Payroll/算薪/薪资包管理" --headless

产物（写到 --out 目录）：
    01_login.png        登录前截图（需要扫码时用）
    02_page.png         目标页面截图
    page.html           目标页面完整 HTML（离线翻 DOM）
    candidates.json     候选定位器：输入框 / 按钮 / 表头 / 首行单元格 / 菜单项
说明：
    - 登录态复用 reports/auth/<环境>_<域名>.json；过期则等待人工扫码（默认 300 秒）
    - 扫码成功后自动刷新登录态文件，后续框架用例直接复用
"""
import argparse
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

from urllib.parse import urlparse  # noqa: E402

from playwright.sync_api import sync_playwright  # noqa: E402

JS_INPUTS = """
() => Array.from(document.querySelectorAll('input')).map(el => ({
  placeholder: el.getAttribute('placeholder'),
  id: el.id || null,
  name: el.getAttribute('name') || null,
  type: el.type,
  cls: el.className,
  visible: !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length),
  formItemLabel: (() => {
     const item = el.closest('.ant-form-item');
     if (!item) return null;
     const label = item.querySelector('label, .ant-form-item-label');
     return label ? label.innerText.trim().replace(/\\s+/g, ' ') : null;
  })()
}))
"""

JS_BUTTONS = """
() => Array.from(document.querySelectorAll('button')).map(el => ({
  text: (el.innerText || '').trim(),
  cls: el.className,
  visible: !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length)
})).filter(b => b.visible)
"""

JS_TABLE = """
() => {
  const t = document.querySelector('.ant-table');
  if (!t) return null;
  const headers = Array.from(t.querySelectorAll('thead th')).map(th => (th.innerText || '').trim());
  const rows = Array.from(t.querySelectorAll('tbody tr')).slice(0, 3).map(tr =>
     Array.from(tr.querySelectorAll('td')).map(td => (td.innerText || '').trim()));
  return {headers, rows};
}
"""

JS_MENU = """
() => Array.from(document.querySelectorAll('li, a, span')).map(el => (el.innerText || '').trim())
        .filter(t => t && t.length < 12).filter((v, i, a) => a.indexOf(v) === i).slice(0, 200)
"""


def auth_file(env, url):
    host = urlparse(url).netloc.replace(":", "_") or "default"
    return os.path.join(paths.AUTH_STATE, f"{env}_{host}.json")


def dump(page, out_dir, tag):
    data = {
        "url": page.url,
        "title": page.title(),
        "inputs": page.evaluate(JS_INPUTS),
        "buttons": page.evaluate(JS_BUTTONS),
        "table": page.evaluate(JS_TABLE),
        "menu_texts": page.evaluate(JS_MENU),
    }
    with open(os.path.join(out_dir, f"candidates_{tag}.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    with open(os.path.join(out_dir, f"page_{tag}.html"), "w", encoding="utf-8") as f:
        f.write(page.content())
    page.screenshot(path=os.path.join(out_dir, f"page_{tag}.png"), full_page=True)
    return data


def click_text(page, text, timeout=8000):
    """按可见文本点击（按钮等通用场景），返回是否点到"""
    deadline = time.time() + timeout / 1000
    while time.time() < deadline:
        for getter in (lambda: page.get_by_text(text, exact=True),
                       lambda: page.get_by_text(text)):
            loc = getter()
            try:
                n = loc.count()
            except Exception:                     # noqa: BLE001
                n = 0
            for i in range(min(n, 5)):
                try:
                    item = loc.nth(i)
                    if item.is_visible():
                        item.click(timeout=3000)
                        return True
                except Exception:                 # noqa: BLE001
                    continue
        page.wait_for_timeout(500)
    return False


def click_menu(page, text, timeout=8000):
    """点击左侧菜单项（antd pro 菜单）

    菜单是多级结构：一级/二级是 .ant-menu-submenu-title（点开展开），叶子是 .ant-menu-item。
    用「精确匹配文本」定位，避免 '算薪' 误点到 '算薪日历' / '算薪数据源'。
    """
    pattern = re.compile(r"^\s*%s\s*$" % re.escape(text))
    deadline = time.time() + timeout / 1000
    while time.time() < deadline:
        # 先试可展开的子菜单标题，再试叶子项
        for selector in (".ant-menu-submenu-title", ".ant-menu-item"):
            try:
                loc = page.locator(selector).filter(has_text=pattern)
                count = loc.count()
            except Exception:                     # noqa: BLE001
                continue
            for i in range(min(count, 6)):
                item = loc.nth(i)
                try:
                    if item.is_visible():
                        item.click(timeout=4000)
                        return True
                except Exception:                 # noqa: BLE001
                    continue
        page.wait_for_timeout(500)
    return False


def ensure_login(page, ctx, base_url, state_file, wait_seconds):
    page.goto(f"{base_url.rstrip('/')}/home", wait_until="domcontentloaded")
    page.wait_for_timeout(2500)
    if "/login" not in page.url:
        print("[login] 登录态有效，直接使用")
        return True
    print(f"[login] 登录态已过期，请在浏览器窗口用企业微信扫码（最多等 {wait_seconds} 秒）")
    print("[login] 当前 URL:", page.url)
    deadline = time.time() + wait_seconds
    while time.time() < deadline:
        page.wait_for_timeout(2000)
        if "/login" not in page.url:
            page.wait_for_timeout(2500)
            ctx.storage_state(path=state_file)
            print("[login] 扫码成功，登录态已保存到", state_file)
            return True
    print("[login] 等待扫码超时")
    return False


def main():
    parser = argparse.ArgumentParser(description="登录现场采集：导航并导出候选定位器")
    parser.add_argument("--url", default="", help="目标页面 URL（不传则用 --menu 导航）")
    parser.add_argument("--menu", default="", help="菜单路径，如 'Payroll/薪资包管理'")
    parser.add_argument("--out", default=os.path.join(paths.REPORTS, "_probe"))
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--wait", type=int, default=300, help="等待人工扫码的秒数")
    parser.add_argument("--query", default="", help="可选：在某输入框输入关键字后点搜索，用于验证结果")
    args = parser.parse_args()

    env = os.getenv("ENV", "测试环境")
    base_url = {"测试环境": "https://test-admin.gsrtech.com",
                "预生产环境": "https://stage-admin.gsrtech.com",
                "生产环境": "https://admin.gsrtech.com"}[env]
    os.makedirs(args.out, exist_ok=True)
    state_file = auth_file(env, base_url)
    os.makedirs(os.path.dirname(state_file), exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=args.headless, slow_mo=120)
        ctx = browser.new_context(locale="zh-CN", viewport={"width": 1600, "height": 900},
                                  storage_state=state_file if os.path.isfile(state_file) else None)
        page = ctx.new_page()
        page.set_default_timeout(20000)

        if not ensure_login(page, ctx, base_url, state_file, args.wait):
            page.screenshot(path=os.path.join(args.out, "01_login.png"))
            browser.close()
            return 2

        if args.url:
            page.goto(args.url, wait_until="domcontentloaded")
            page.wait_for_timeout(4000)
        elif args.menu:
            for part in [p for p in args.menu.split("/") if p]:
                print("[nav] 点击菜单:", part)
                if not click_menu(page, part):
                    print("[nav] 未找到菜单项:", part)
                    dump(page, args.out, "menu_fail")
                    browser.close()
                    return 3
                page.wait_for_timeout(1800)
            page.wait_for_timeout(3000)
        print("[nav] 当前 URL:", page.url)

        data = dump(page, args.out, "target")
        print("[dump] URL:", data["url"])
        print("[dump] 表头:", data["table"]["headers"] if data["table"] else None)
        print("[dump] 首行:", data["table"]["rows"][0] if data["table"] and data["table"]["rows"] else None)
        print("[dump] 输入框:", [i["placeholder"] or i["id"] for i in data["inputs"]])
        print("[dump] 按钮:", [b["text"] for b in data["buttons"]])

        if args.query:
            # 在「薪资包ID」输入框输入关键字并搜索（示例：placeholder 含 SAL 或标签为薪资包ID）
            target = None
            for item in data["inputs"]:
                label = (item.get("formItemLabel") or "")
                ph = (item.get("placeholder") or "")
                if "SAL" in ph.upper() or "薪资包ID" in label.replace(" ", ""):
                    target = item
                    break
            if target:
                sel = f"#{target['id']}" if target.get("id") else f"input[placeholder='{target['placeholder']}']"
                page.fill(sel, args.query)
                page.wait_for_timeout(500)
                click_text(page, "搜索")
                page.wait_for_timeout(4000)
                after = dump(page, args.out, "after_query")
                print("[query] 搜索后首行:", after["table"]["rows"][0] if after["table"] and after["table"]["rows"] else None)
            else:
                print("[query] 没找到薪资包ID输入框")

        ctx.storage_state(path=state_file)
        browser.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
