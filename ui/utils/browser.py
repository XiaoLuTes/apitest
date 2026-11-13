import os
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright
from ui.utils.logger import logger
from ui.config.settings import settings

def auth_state_file_path():
    """登录态文件路径: <项目根>/reports/auth/<环境>_<域名>.json
    按“环境 + 域名”区分：同一域名下所有项目共用一份登录态（切换项目不用重扫码）
    """
    folder = settings.AUTH_STATE_DIR
    if not os.path.isabs(folder):
        folder = os.path.join(settings.PROJECT_ROOT, folder)
    os.makedirs(folder, exist_ok=True)
    host = urlparse(settings.URL).netloc.replace(":", "_") or "default"
    return os.path.join(folder, f"{settings.ENV}_{host}.json")


class BrowserEngine:
    _instance = None

    def __new__(cls):
        if not cls._instance:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        # __new__ 返回已有实例时 Python 仍会调用 __init__，
        # 这里必须提前返回，否则会把 playwright/browser/context/page 重置为 None
        if getattr(self, "_initialized", False):
            return
        self._initialized = True
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None

    def start_browser(self):
        self.playwright = sync_playwright().start()

        browser_type = settings.BROWSER.lower()
        headless = settings.HEADLESS
        slow_mo = settings.SLOW_MO

        if browser_type in ["chrome", "chromium"]:
            self.browser = self.playwright.chromium.launch(headless=headless, slow_mo=slow_mo)
        elif browser_type == "firefox":
            self.browser = self.playwright.firefox.launch(headless=headless, slow_mo=slow_mo)
        elif browser_type == "webkit":
            self.browser = self.playwright.webkit.launch(headless=headless, slow_mo=slow_mo)
        else:
            raise Exception(f"不支持的浏览器: {browser_type}")

        # 复用上次保存的登录态（cookie + localStorage），没有就当作首次登录
        state_path = self.auth_state_path()
        use_state = os.path.isfile(state_path)
        self.context = self.browser.new_context(
            locale="zh-CN",
            viewport=settings.BROWSER_VIEWPORT,
            storage_state=state_path if use_state else None
        )
        logger.info(f"已加载登录态文件: {state_path}" if use_state else "未找到登录态文件,本次需首次登录")
        self.context.set_default_timeout(settings.IMPLICIT_WAIT)
        self.page = self.context.new_page()

        logger.info("Playwright 浏览器启动完成")
        return self.page

    def auth_state_path(self):
        """登录态文件路径（实现见模块级函数 auth_state_file_path）"""
        return auth_state_file_path()

    def stop_browser(self):
        if self.context:
            self.context.close()
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()
        logger.info("Playwright 浏览器已关闭")
