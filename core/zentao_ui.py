# -*- coding: utf-8 -*-
"""禅道表单操作（浏览器侧）：补传附件

为什么需要它：公司禅道（22.6）的 REST 附件接口 POST /api.php/v1/files 对 png/xlsx/txt
一律返回"文件格式不在规定范围内"，但**页面表单上传是正常的**。
所以附件走浏览器：登录 → 打开 bug-edit-{id}.html → 选择文件 → 保存。
"""
import os
import threading

from playwright.sync_api import sync_playwright


def _find_form_frame(page):
    for frame in page.frames:
        try:
            if "重现步骤" in frame.inner_text("body") or "Bug标题" in frame.inner_text("body"):
                return frame
        except Exception:                        # noqa: BLE001
            continue
    return None


def upload_attachments(bug_id, paths, base_url, account, password,
                       headless=True, timeout=30000, wait_after_save=4000):
    """把本地文件作为附件上传到指定缺陷（在线程里跑，避免与调用方的 Playwright 同步 API 冲突）

    注意：如果调用方已经用 sync_playwright 跑着浏览器（比如 UI 用例刚采完证据），
    同线程内再开一个 sync_playwright 会报
    "It looks like you are using Playwright Sync API inside the asyncio loop"。
    放到独立线程执行即可规避。

    :return: 实际上传的文件名列表
    """
    paths = [p for p in (paths or []) if p and os.path.isfile(p)]
    if not paths:
        return []

    holder = {}

    def _worker():
        try:
            holder["files"] = _upload_sync(bug_id, paths, base_url, account, password,
                                           headless, timeout, wait_after_save)
        except Exception as exc:                  # noqa: BLE001
            holder["error"] = exc

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()
    thread.join()
    if "error" in holder:
        raise holder["error"]
    return holder.get("files") or []


def _upload_sync(bug_id, paths, base_url, account, password, headless, timeout, wait_after_save):

    base_url = base_url.rstrip("/")
    uploaded = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        ctx = browser.new_context(viewport={"width": 1500, "height": 1000}, locale="zh-CN")
        page = ctx.new_page()
        page.set_default_timeout(timeout)
        page.goto(f"{base_url}/user-login.html", wait_until="domcontentloaded")
        page.fill("#account", account)
        page.fill("#password", password)
        page.click("#submit")
        page.wait_for_timeout(3500)

        page.goto(f"{base_url}/bug-edit-{bug_id}.html", wait_until="domcontentloaded")
        page.wait_for_timeout(4000)
        frame = _find_form_frame(page)
        if frame is None:
            browser.close()
            raise RuntimeError(f"未找到缺陷编辑表单（bug-edit-{bug_id}.html），无法上传附件")

        for path in paths:
            frame.set_input_files("input[name='files[]']", path)
            page.wait_for_timeout(2000)
            uploaded.append(os.path.basename(path))

        frame.click("xpath=//button[contains(., '保存')]")
        page.wait_for_timeout(wait_after_save)
        print(f"[附件] 已上传 {len(uploaded)} 个文件到缺陷 #{bug_id}：{', '.join(uploaded)}")
        browser.close()
    return uploaded
