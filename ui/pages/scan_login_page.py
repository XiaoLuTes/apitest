import hashlib
import os
import time

import allure
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from ui.pages.base_page import BasePage
from ui.utils.logger import logger


class ScanLoginPage(BasePage):
    """扫码登录基类（企业微信 / 钉钉 / 飞书等无法自动填表的登录方式通用）

    子类必须指定：
        LOGGED_IN_URL  登录成功后 URL 的特征（re.Pattern 或字符串）
    子类可选覆盖：
        ENTRY_URL      登录入口地址，None 表示用 settings.URL
        after_login()  登录成功后的收尾动作（如点“进入管理平台”）
    """

    LOGGED_IN_URL = None      # 子类必须覆盖，否则 is_logged_in 直接报错
    ENTRY_URL = None          # None -> settings.URL

    # ===== 登录二维码位置（子类按自己系统的登录页覆盖）=====
    # None 表示未配置：此时不做元素级截图，直接回退整页截图
    QR_IFRAME_SELECTOR = None     # 二维码所在 iframe 的选择器
    QR_SELECTOR = None            # iframe 内二维码元素的选择器
    QR_PUSH_INTERVAL = 60         # 二维码刷新/重新推送时间（s）

    # ===== “假登录”识别：cookie 过期时 URL 仍会命中登录路由，但页面会弹过期提示 =====
    # 换系统时在子类覆盖；设为空元组则跳过该检测
    SESSION_EXPIRED_TEXTS = ("重新登录",)
    # 弹窗可能在 URL 变化后几百毫秒才渲染出来，检测轮询时长（毫秒）
    SESSION_EXPIRED_CHECK_MS = 1200

    def __init__(self, page_name, page):
        super().__init__(page_name, page)
        self._last_qr_hash = None      # 上次推送的二维码内容 md5，用于判断是否需要重推

    def entry_url(self):
        """登录入口地址"""
        return self.ENTRY_URL or self.settings.URL

    # ==================== 登录态判定 ====================
    def is_logged_in(self, timeout=None):
        """判定登录态：URL 命中 LOGGED_IN_URL 即算已登录（唯一判定依据）"""
        if not self.LOGGED_IN_URL:
            raise Exception(f"{type(self).__name__} 未配置 LOGGED_IN_URL，无法判定登录态")
        timeout = self.settings.LOGIN_CHECK_TIMEOUT if timeout is None else timeout
        try:
            self.page.wait_for_url(self.LOGGED_IN_URL, timeout=timeout)
        except PlaywrightTimeoutError:
            return False

        # 路由命中不代表真的登录：cookie 过期时同样会跳到 /statistics，然后弹“登录状态已过期”
        expired_text = self.wait_session_expired_prompt()
        if expired_text:
            logger.warning(f"命中登录路由但出现过期提示「{expired_text}」，判定为未登录")
            return False

        logger.info(f"登录态有效（路由命中）: {self.page.url}")
        return True

    def wait_session_expired_prompt(self):
        """轮询检测“登录已过期”类弹窗，返回命中的文案；未命中返回 None"""
        texts = [t for t in self.SESSION_EXPIRED_TEXTS if t]
        if not texts:
            return None
        deadline = time.time() + self.SESSION_EXPIRED_CHECK_MS / 1000
        while True:
            for text in texts:
                try:
                    if self.page.get_by_text(text).first.is_visible():
                        return text
                except PlaywrightError:
                    continue
            if time.time() >= deadline:
                return None
            self.page.wait_for_timeout(200)

    def after_login(self):
        """登录成功后的收尾动作，默认无操作，子类按需覆盖"""
        return True

    def wait_for_manual_login(self):
        """打开入口页等人工扫码，用路由变化确认登录成功"""
        total = int(self.settings.LOGIN_WAIT_TIMEOUT)
        if total <= 0:
            raise Exception(
                "登录态已失效，且 LOGIN_WAIT_TIMEOUT=0（不允许等待人工扫码）。")
        self.clear_auth_state()
        self.open(self.entry_url())
        self.page.wait_for_timeout(2000)          # 等二维码渲染

        # 决策：企业微信推送可用就推二维码（有头无头都推）；不可用且无头则直接中断
        reason = self.settings.wecom_disabled_reason()
        if reason and self.settings.HEADLESS:
            raise Exception(
                f"登录态失效，且企业微信推送不可用（{reason}），无头模式下二维码无法送达，已中断。"
                "请检查 WECOM_ENABLE / WECOM_WEBHOOK，或本地以有头模式运行一次刷新登录态")

        logger.warning("=" * 66)
        if reason:
            logger.warning(f"登录态已失效，企业微信推送不可用（{reason}），"
                           f"请在弹出的浏览器中【扫码登录】，最多等待 {total} 秒")
        else:
            pushed = self.push_qr_code()
            if pushed:
                logger.warning(f"登录态已失效，二维码已推送到企业微信群，请扫码（最多等待 {total} 秒）")
            elif self.settings.HEADLESS:
                logger.warning("=" * 66)
                raise Exception(
                    "二维码推送企业微信失败，且当前为无头模式（无人能看到二维码），已中断。"
                    "请检查 WECOM_ENABLE / WECOM_WEBHOOK 是否正确")
            else:
                logger.warning("二维码推送失败，请在浏览器窗口直接扫码（推送不影响本地扫码）")
        logger.warning("=" * 66)

        start_time = time.time()
        last_log = 0
        last_qr_check = start_time
        while time.time() - start_time < total:
            if self.is_logged_in(timeout=3000):  # 轮询登录状态，3s一次
                elapsed = int(time.time() - start_time)
                logger.info(f"扫码登录成功，耗时 {elapsed} 秒，当前URL: {self.page.url}")
                self.after_login()
                self.save_auth_state()
                self.notify_login_success(elapsed)
                return True
            waited = int(time.time() - start_time)
            if waited - last_log >= 15:            # 每 15 秒提示一次，避免刷屏
                logger.warning(f"仍在等待扫码... 已等待 {waited}/{total} 秒")
                last_log = waited
            # 二维码会过期刷新：配了群机器人时，内容变了就重推一次
            if not reason and time.time() - last_qr_check >= self.QR_PUSH_INTERVAL:
                last_qr_check = time.time()
                self.push_qr_code(only_if_changed=True)
            self.page.wait_for_timeout(1000)

        if not reason:
            raise Exception(f"等待扫码登录超时（{total} 秒）：二维码已推送到企业微信群，无人扫码")
        raise Exception(f"等待扫码登录超时（{total} 秒）：请确认浏览器已弹出、二维码已正常渲染")

    # ==================== 无头模式：二维码推送 ====================
    def _capture_qr_image(self):
        """截取登录二维码；失败时回退整页截图，返回文件路径（失败返回 None）"""
        folder = self.settings.SCREENSHOT_PATH
        os.makedirs(folder, exist_ok=True)
        # 文件名带页面前缀：同一项目下多个登录页各自一份，固定名覆盖写，不会越积越多
        safe_page = "".join(c if c.isalnum() or c in "-_" else "_" for c in str(self.page_name))
        path = os.path.join(folder, f"{safe_page}_登录二维码.png")
        if self.QR_IFRAME_SELECTOR and self.QR_SELECTOR:
            try:
                frame = self.page.frame_locator(self.QR_IFRAME_SELECTOR).first
                qr = frame.locator(self.QR_SELECTOR).first
                qr.wait_for(state="visible", timeout=8000)
                qr.screenshot(path=path)  # 按元素裁剪
                logger.info(f"二维码已截取: {path}")
                return path
            except (PlaywrightError, OSError) as e:
                logger.warning(f"按定位器截取二维码失败({e})，回退整页截图")
        else:
            logger.warning("未配置 QR_IFRAME_SELECTOR / QR_SELECTOR，直接回退整页截图")
        try:
            self.page.screenshot(path=path, full_page=True)
            return path
        except (PlaywrightError, OSError) as e:
            logger.error(f"二维码截图失败: {e}")
            return None

    def push_qr_code(self, only_if_changed=False):
        """把登录二维码推送到企业微信群（无头模式下唯一能看到二维码的途径）
        :param only_if_changed: True 时仅在二维码内容变化后才重推（仅适用于二维码过期会自动刷新）
        """
        image_path = self._capture_qr_image()
        if not image_path:
            return False
        try:
            with open(image_path, "rb") as f:
                digest = hashlib.md5(f.read()).hexdigest()
        except OSError as e:
            logger.warning(f"读取二维码文件失败: {e}")
            digest = None
        if only_if_changed and digest and digest == self._last_qr_hash:
            return False
        self._last_qr_hash = digest

        reason = self.settings.wecom_disabled_reason()
        if reason:
            logger.warning(f"企业微信推送不可用（{reason}），无法推送二维码（已保存到 {image_path}）")
            return False
        from ui.utils.wecom import send_image, send_markdown
        ok = send_image(self.settings.WECOM_WEBHOOK, image_path)
        send_markdown(self.settings.WECOM_WEBHOOK, f"登录态已失效，请扫码，当前环境为：{self.settings.ENV}")
        if ok:
            logger.warning("二维码已推送到企业微信群，请用【企业微信】扫码登录（过期会自动重推）")
        return ok

    def notify_login_success(self, elapsed=0):
        """扫码成功后回群里通知一声（未配置群机器人则跳过）"""
        if self.settings.wecom_disabled_reason():
            return
        try:
            from ui.utils.wecom import send_markdown
        except ImportError as e:
            logger.warning(f"登录成功通知发送失败（wecom 模块不可用）: {e}")
            return
        send_markdown(self.settings.WECOM_WEBHOOK, f"## 已扫码登录成功\n> 耗时 {elapsed} 秒\n> 用例继续执行")

    def clear_auth_state(self):
        """清掉失效的登录态：磁盘 cookie 文件 + 浏览器 cookie/localStorage
        """
        try:
            from ui.utils.browser import auth_state_file_path
            path = auth_state_file_path()
            if os.path.isfile(path):
                os.remove(path)
                logger.warning(f"已删除失效的登录态文件: {path}")
        except OSError as e:
            logger.warning(f"删除登录态文件失败（不影响后续扫码）: {e}")

        try:
            self.page.context.clear_cookies()
        except PlaywrightError as e:
            logger.warning(f"清除浏览器 cookie 失败: {e}")

        # 清本地存储
        try:
            self.page.evaluate(
                "() => { try { localStorage.clear(); sessionStorage.clear(); } catch (e) {} }")
        except PlaywrightError as e:
            logger.warning(f"清除浏览器本地存储失败: {e}")

    def save_auth_state(self):
        """保存当前cookie，供下次运行复用
        直接用当前 page 所属的 context 保存，不经过 BrowserEngine 单例：
        """
        try:
            from ui.utils.browser import auth_state_file_path
            path = auth_state_file_path()
            self.page.context.storage_state(path=path)
            logger.info(f"登录态已保存: {path}")
        except (PlaywrightError, OSError) as e:
            logger.warning(f"登录态保存失败（不影响本次执行）: {e}")

    @allure.step("确保已登录状态")
    def ensure_logged_in(self):
        try:
            # 当前页就是登录态 -> 直接过，不重新导航
            if self.is_logged_in(timeout=5000):
                logger.info("登录态有效，跳过登录检查，保存当前可用cookie")
                self.save_auth_state()
                return True

            # 确认失效 -> 等人工扫码
            logger.warning("登录态已失效，进入人工扫码流程")
            return self.wait_for_manual_login()

        except Exception as e:   # 兜住所有异常：先截图留证，再原样抛出，不吞异常
            logger.error(f"登录状态检查失败: {str(e)}")
            self.take_screenshot("登录状态异常")
            raise
