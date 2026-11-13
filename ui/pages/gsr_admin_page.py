import re
from ui.pages.scan_login_page import ScanLoginPage
from ui.utils.logger import logger


class GsrAdminPage(ScanLoginPage):
    """GSR 管理端（企业微信扫码登录）
    """
    # 登录成功后 URL 会命中：无缓存时先到系统选择页 /sys，有缓存时直达 /statistics
    LOGGED_IN_URL = re.compile(r"/sys|/statistics")

    # 企业微信扫码登录页：二维码在 login.work.weixin.qq.com 的 iframe 内，元素 192x192
    QR_IFRAME_SELECTOR = "iframe"
    QR_SELECTOR = "img.wwLogin_qrcode_img"

    def after_login(self):
        """停在系统选择页 /sys 时，点一次“管理平台”进入管理端"""
        if "/sys" in self.page.url:
            logger.info("检测到系统选择页，点击进入管理平台")
            self.element_click("management_button")
            self.wait_if_loading()
        return True
