from ui.utils.logger import logger
from ui.config.settings import settings
import importlib


class PageManager:
    """页面对象管理器 - 动态管理多个页面对象（Playwright 版）"""

    def __init__(self, page):
        self.page = page
        self.pages = {}
        self.settings = settings

    def register_page(self, page_name, page_class=None):
        """注册页面对象"""
        if page_class is None:
            page_class = self.import_page_class(page_name)
        if page_class:
            page_instance = page_class(page_name, self.page)
            if hasattr(page_instance, 'set_page_manager'):
                page_instance.set_page_manager(self)
            self.pages[page_name] = page_instance
            logger.info(f"注册页面对象: {page_name}")
            return page_instance
        else:
            from ui.pages.base_page import BasePage
            page_instance = BasePage(page_name, self.page)
        self.pages[page_name] = page_instance
        logger.info(f"注册页面对象: {page_name}")
        return page_instance

    def import_page_class(self, page_name):
        """动态导入页面类"""
        try:
            class_mapping = settings.PAGE_CLASSES
            class_name = class_mapping.get(page_name)
            if not class_name:
                return None
            module_path = f"ui.pages.{page_name}"
            module = importlib.import_module(module_path)
            page_class = getattr(module, class_name)
            return page_class
        except Exception as e:
            logger.error(f"导入页面类失败 {page_name}: {str(e)}")
            return None

    def get_page(self, page_name):
        """获取页面对象"""
        if page_name in self.pages:
            return self.pages[page_name]
        else:
            logger.warning(f"页面对象未注册: {page_name}, 尝试动态注册")
            return self.register_page(page_name)

    def navigate_to_page(self, page_name):
        """导航到指定页面"""
        page_url = self.settings.PAGE_URLS.get(page_name)
        if page_url:
            page_obj = self.get_page(page_name)
            page_obj.open(page_url)

            return True
        else:
            logger.error(f"未找到页面 {page_name} 的URL配置")
            return False
