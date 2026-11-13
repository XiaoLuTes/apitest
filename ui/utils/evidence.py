# -*- coding: utf-8 -*-
"""执行证据采集器：真实步骤 + 接口请求/返回 + 页面截图

用途：UI 用例失败、或需要"人看得懂"的缺陷证据时，用它把一次真实操作过程完整记录下来，
再交给 tools/evidence_bug.py 生成缺陷单。示例见 tools/demo_pkg_search.py。

用法：
    rec = EvidenceRecorder(page, api_keywords=["/payrollSalaryPackage/list"]).start()
    rec.step("1、打开薪资包管理页面", action="open")
    rec.step("2、输入薪资包ID", action="input", element="pkg_code_input", data="测试不存在code")
    rec.screenshot("搜索后列表为空")
    rec.stop()
    rec.dump("reports/evidence/demo.json")
"""
import json
import os
import time

from core import paths
from ui.utils.logger import logger


class EvidenceRecorder:
    def __init__(self, page, api_keywords=None, title="", case_id="", screenshot_dir=None):
        self.page = page
        self.api_keywords = list(api_keywords or [])
        self.title = title
        self.case_id = case_id
        self.steps = []
        self.api_calls = []
        self.screenshots = []
        self.screenshot_dir = screenshot_dir or paths.SCREENSHOTS
        os.makedirs(self.screenshot_dir, exist_ok=True)
        self._handler = None

    # ---------------- 生命周期 ----------------
    def start(self):
        """开始记录接口调用（按 api_keywords 过滤，留空=记录全部）"""

        def _on_response(resp):
            try:
                if self.api_keywords and not any(k in resp.url for k in self.api_keywords):
                    return
                request = resp.request
                try:
                    body = resp.text()
                except Exception:                    # noqa: BLE001
                    body = ""
                self.api_calls.append({
                    "method": request.method,
                    "url": resp.url,
                    "request_body": (request.post_data or "")[:2000],
                    "status": resp.status,
                    "response": (body or "")[:4000],
                })
            except Exception:                        # noqa: BLE001
                pass

        self._handler = _on_response
        self.page.on("response", self._handler)
        return self

    def stop(self):
        if self._handler:
            try:
                self.page.remove_listener("response", self._handler)
            except Exception:                        # noqa: BLE001
                pass
            self._handler = None

    # ---------------- 记录 ----------------
    def step(self, name, action="", element="", data="", note=""):
        self.steps.append({
            "index": len(self.steps) + 1,
            "name": name, "action": action, "element": element,
            "data": "" if data is None else str(data)[:500], "note": note,
        })
        logger.info(f"[证据] 步骤{len(self.steps)}: {name}")
        return self

    def screenshot(self, name, full_page=True):
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in str(name))
        stamp = time.strftime("%Y%m%d_%H%M%S")
        path = os.path.join(self.screenshot_dir, f"{safe}_{stamp}.png")
        try:
            self.page.screenshot(path=path, full_page=full_page)
            self.screenshots.append(path)
            logger.info(f"[证据] 截图: {path}")
        except Exception as e:                       # noqa: BLE001
            logger.warning(f"[证据] 截图失败: {e}")
        return path

    def last_api(self, keyword=""):
        for call in reversed(self.api_calls):
            if not keyword or keyword in call["url"]:
                return call
        return None

    # ---------------- 输出 ----------------
    def to_dict(self, extra=None):
        data = {
            "title": self.title,
            "case_id": self.case_id,
            "captured_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "env": (os.getenv("ENV") or "测试环境"),
            "url": getattr(self.page, "url", ""),
            "steps": self.steps,
            "api_calls": self.api_calls,
            "screenshots": self.screenshots,
        }
        if extra:
            data.update(extra)
        return data

    def dump(self, path=None, extra=None):
        data = self.to_dict(extra)
        if path is None:
            os.makedirs(os.path.join(paths.REPORTS, "evidence"), exist_ok=True)
            stem = (self.case_id or "evidence").replace("/", "_").replace("\\", "_")
            path = os.path.join(paths.REPORTS, "evidence",
                                f"{stem}_{time.strftime('%Y%m%d_%H%M%S')}.json")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"[证据] 已保存: {path}")
        return path
