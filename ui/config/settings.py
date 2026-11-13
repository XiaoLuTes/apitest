import os
import time

from core import paths
from core.env import load_env

# 统一从仓库根目录的 .env 读取（系统环境变量优先级更高，会覆盖 .env）
load_env()
# UI 用例集根目录：autotest/ui（本文件位于 ui/config/settings.py）
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

class Settings:
    """支持环境变量覆盖的配置类"""

    def __init__(self):
        # 环境配置
        self.ENV = self._get_env_var("ENV", "测试环境")
        # 不同环境的基础URL配置
        self.BASE_URLS = {
            "生产环境": "https://admin.gsrtech.com",
            "预生产环境": "https://stage-admin.gsrtech.com/",
            "测试环境": "https://test-admin.gsrtech.com/"
        }
        self.OMIN_URLS = {
            "生产环境": "",
            "预生产环境": "",
            "测试环境": "https://test-omni.gsrtech.com/"
        }
        self.URL = self.BASE_URLS[self.ENV]
        self.OMIN_URL = self.OMIN_URLS[self.ENV]
        # 不同环境的客户名称数据
        self.CUSTOMERS = {
            "测试环境": "louie测试1号客户",
            "预生产环境": "高斯全球B（演示用）",
            "生产环境": "高斯全球B（演示用）"
        }
        self.OWNERS = {
            "测试环境": "卢毅",
            "预生产环境": "黄伟龙",
            "生产环境": "卢毅"
        }
        self.CUSTOMER = self.CUSTOMERS[self.ENV]
        self.OWNER = self.OWNERS[self.ENV]

        # 项目配置
        self.PROJECT_CONFIGS = {
            "招聘平台新建岗位": {
                "PAGE_NAME": ["gsr_admin_page"],  # 页面对象
                "TESTCASES_PATH": "./testcases/pt_new_position/pt_testcases.yaml",  # 测试用例路径
                "ELEMENT_LOCATORS": "./config/locators/new_position_element_locators.yaml",  # 元素定位器路径
                "description": "招聘平台非eor岗位全流程",  # 项目描述
                "LOADING_SELECTOR": ""  # 项目页面加载项(需要等待加载完成的),填CSS id选择器,不需要等待则不填
            },
            "招聘平台新建编制": {
                "PAGE_NAME": ["gsr_admin_page"],
                "TESTCASES_PATH": "./testcases/pt_new_preparation/new_preparation.yaml",
                "ELEMENT_LOCATORS": "./config/locators/gsr_admin_page.yaml",
                "description": "招聘平台新发起编制流程"
            },
            # 临时停用：用例文件 ui/testcases/pt_new_position_v2/pt_testcases_v2.yaml 不存在
            # （lint 会报"用例文件不存在"）。补回该 yaml 后取消下面注释即可恢复。
            # "招聘平台新建岗位-维护版": {
            #     "PAGE_NAME": ["login_page", "gsr_admin_page"],
            #     "TESTCASES_PATH": "./testcases/pt_new_position_v2/pt_testcases_v2.yaml",
            #     "ELEMENT_LOCATORS": "./config/locators/pt_new_position_v2.yaml",
            #     "description": "招聘平台新建岗位全流程（维护版，重新采集元素）"
            # },
            "薪资包管理查询": {
                "PAGE_NAME": ["payroll_package_page"],  # 页面对象
                "TESTCASES_PATH": "./testcases/payroll_package/package_query.yaml",  # 测试用例路径
                "ELEMENT_LOCATORS": "./config/locators/payroll_package_management.yaml",  # 元素定位器路径
                "description": "Payroll-算薪-薪资包管理：按薪资包ID查询（接口 + UI 双层）",
                "LOADING_SELECTOR": "#loader-wrapper"
            },
            "薪资结算包收款包链路": {
                "PAGE_NAME": ["gsr_admin_page"],
                "TESTCASES_PATH": "./testcases/eor_salary_ettlement/salary_payment_collection_v2.yaml",
                "ELEMENT_LOCATORS": "./config/locators/gsr_admin_page_management.yaml",
                "description": "薪资结算包收款包单月发起引用链路",
                "LOADING_SELECTOR": "#loader-wrapper"
            }
        }
        # 页面url映射
        self.PAGE_URLS = {
            "gsr_admin_page": self.URL,  # 管理端首页URL（导航时自动登录）
            "payroll_package_page": self.URL.rstrip("/") + "/center/payroll/payrollSalary/packageManagement",
            "login_page": self.URL  # 登录页URL（不做自动登录，用于显式测试登录表单）
            # 可以继续添加其他页面的URL配置...
        }
        # 页面类映射
        self.PAGE_CLASSES = {
            "gsr_admin_page": "GsrAdminPage",
            "payroll_package_page": "PayrollPackagePage"
        }
        # 获取当前项目
        # 项目名解析优先级：UI_PROJECT > CURRENT_PROJECT（两个用例集共用一份 .env）
        self.CURRENT_PROJECT = os.getenv("UI_PROJECT") or self._get_env_var(
            "CURRENT_PROJECT", '薪资结算包收款包链路')
        if self.CURRENT_PROJECT not in self.PROJECT_CONFIGS:
            if os.getenv("UI_PROJECT"):
                raise SystemExit("[配置错误] UI_PROJECT=%r 不是 UI 用例集，可选值：%s"
                                 % (self.CURRENT_PROJECT, "、".join(self.PROJECT_CONFIGS)))
            print(f"[配置提示] CURRENT_PROJECT={self.CURRENT_PROJECT!r} 不是 UI 用例集，回落到默认项目")
            self.CURRENT_PROJECT = "招聘平台新建岗位"
        # 获取当前项目配置
        self.PROJECT_CONFIG = self.get_current_project_config(self.CURRENT_PROJECT)
        # 测试用例文件位置(根据项目获取)
        self.TESTCASES = paths.resolve(self.PROJECT_CONFIG["TESTCASES_PATH"], PROJECT_ROOT)
        # 复用测试用例文件位置(写回步骤测试结果，防止污染用例)
        self.TEST_RESULT_DIR = self._get_env_var("TEST_RESULT_DIR", paths.RESULTS_UI)
        # 页面名称(根据项目获取)
        self.PAGE_NAME = self.PROJECT_CONFIG["PAGE_NAME"]
        # 项目页面加载项(需要等待加载完成的)CSS id选择器
        self.LOADING_SELECTOR = self.PROJECT_CONFIG.get("LOADING_SELECTOR", "")
        # 默认项目页面
        self.DEFAULT_PAGE_NAME = "gsr_admin_page"
        # 元素定位器地址
        self.ELEMENT_LOCATORS = paths.resolve(self.PROJECT_CONFIG["ELEMENT_LOCATORS"], PROJECT_ROOT)
        # 文件下载路径(当前项目路径)
        self.PROJECT_ROOT = PROJECT_ROOT
        # 下载文件默认目录
        self.DOWNLOAD_DIR = self._get_env_var("DOWNLOAD_DIR", paths.DOWNLOADS)

        # ===================== 账号密码配置 =====================
        #  仅保留给 ddddocr 识别验证码的“账号密码登录”旧链路（或其他项目复用）。
        #  扫码登录态由 AUTH_STATE_DIR 下的 cookie 文件维护，与 LOGIN_USER 无关。
        self.LOGIN_USER = self._get_env_var("LOGIN_USER", '')
        self.PASSWORD = self._get_env_var("PASSWORD", '')

        # ===================== 企业微信通知 =====================
        # 群机器人 Webhook：不配则所有企业微信消息（结果通知 / 登录二维码）都跳过
        self.WECOM_WEBHOOK = self._get_env_var("WECOM_WEBHOOK", "")
        # 总开关：false 时即使配了 Webhook 也一条不发（本地调试不想打扰群时用）
        self.WECOM_ENABLE = self._get_env_var("WECOM_ENABLE", "true").strip().lower() in (
            "true", "1", "yes", "y", "on")

        # 数据库配置
        self.DB_HOST = self._get_env_var("DB_HOST", '')
        self.DB_USER = self._get_env_var("DB_USER", '')
        self.DB_PASSWORD = self._get_env_var("DB_PASSWORD", '')
        self.DB_PORT = self._get_env_var("DB_PORT", '')
        self.DB_NAME = self._get_env_var("DB_NAME", '')

        # ===================== 登录态：免扫码 token 注入 =====================
        # .env 的 ACCESS_TOKEN_ADMIN（浏览器登录后 GSR-Token cookie 的值）直接注入浏览器，
        # 跳过企业微信扫码；token 失效时自动回落到扫码流程。UI_LOGIN_BY_TOKEN=false 可关闭。
        self.ACCESS_TOKEN_ADMIN = self._get_env_var("ACCESS_TOKEN_ADMIN", "")
        self.LOGIN_BY_TOKEN = self._get_env_var("UI_LOGIN_BY_TOKEN", "true").strip().lower() in (
            "true", "1", "yes", "y", "on")

        # ===================== Playwright 配置 =====================
        self.BROWSER = self._get_env_var("BROWSER", "chrome")  # chromium / firefox / webkit
        self.HEADLESS = self._get_env_var("HEADLESS", "False").lower() == "true"  # False=显示浏览器，True=无界面
        self.SLOW_MO = 100  # 操作延迟（调试用）
        self.BROWSER_VIEWPORT = {"width": 1920, "height": 1080}

        # 超时时间设置(毫秒)-隐式超时(page全局)
        self.IMPLICIT_WAIT = int(self._get_env_var("IMPLICIT_WAIT", "15000"))
        # 超时时间设置(秒)-等待元素值变更超时时间
        self.EXPLICIT_WAIT = int(self._get_env_var("EXPLICIT_WAIT", "30"))
        # 等待值变化时的页面刷新间隔(秒)，默认5秒
        self.REFRESH_INTERVAL = int(self._get_env_var("REFRESH_INTERVAL", "5"))
        # 等待元素值变化时，元素不存在超时时间(毫秒)，默认3000毫秒
        self.TIME_FIND = int(self._get_env_var("TIME_FIND", "3000"))
        # 其他时间设置
        self.REFRESH_TIME = int(self._get_env_var("REFRESH_TIME", "15"))
        self.DB_TIMEOUT = int(self._get_env_var("DB_TIMEOUT", "20"))
        self.WAIT_ELEMENT_APPEAR = int(self._get_env_var("WAIT_ELEMENT_APPEAR", "120"))

        # 报告和截图配置
        self.REPORT_PATH = self._get_env_var("REPORT_PATH", paths.REPORTS)
        self.SCREENSHOT_ON_FAILURE = self._get_env_var("SCREENSHOT_ON_FAILURE", "True").lower() == "true"
        self.REPORT_ALLURE = self._get_env_var("REPORT_ALLURE", paths.ALLURE_RESULTS)
        self.CLEAN_HISTORY = self._get_env_var("CLEAN_HISTORY", "True").lower() == "true"
        self.LOG_LEVEL = self._get_env_var("LOG_LEVEL", "INFO")
        self.LOG_FILE = self._get_env_var("LOG_FILE", os.path.join(paths.REPORTS, "ui.log"))
        self.SCREENSHOT_PATH = self._get_env_var("SCREENSHOT_PATH", paths.SCREENSHOTS)

        # ===================== 登录态（企业微信扫码 + cookie 复用）=====================
        # 文件名规则: <环境>_<域名>.json，例如 reports/auth/测试环境_test-admin.gsrtech.com.json
        #   同一域名下所有项目共用一份 cookie（切换项目无需重新扫码）
        self.AUTH_STATE_DIR = self._get_env_var("AUTH_STATE_DIR", paths.AUTH_STATE)
        # 等待人工扫码的最长时间（秒）。0 = 不允许等待（云端/无人值守 Jenkins 用）
        self.LOGIN_WAIT_TIMEOUT = int(self._get_env_var("LOGIN_WAIT_TIMEOUT", "300"))
        # 每条用例前检查登录态的短超时（毫秒）
        self.LOGIN_CHECK_TIMEOUT = int(self._get_env_var("LOGIN_CHECK_TIMEOUT", "8000"))

        # 时间戳设置
        self.TIME_STAMP = int(time.time() * 1000)

        # 打印当前配置（用于调试）
        # self._print_current_config()

    def _get_env_var(self, var_name: str, default: str) -> str:
        """从环境变量获取配置，如果没有则使用默认值"""
        return os.getenv(var_name, default)

    def wecom_disabled_reason(self):
        """返回企业微信推送不可用的原因；返回 None 表示可以推送

        统一判断两个开关：WECOM_ENABLE（总开关，默认 true）、WECOM_WEBHOOK（没配就不发）
        """
        if not self.WECOM_ENABLE:
            return "WECOM_ENABLE=false，企业微信推送已关闭"
        if not self.WECOM_WEBHOOK:
            return "未配置 WECOM_WEBHOOK"
        return None

    def get_current_project_config(self, project_name):
        default_project = "招聘平台新建岗位"
        if project_name in self.PROJECT_CONFIGS:
            return self.PROJECT_CONFIGS[project_name]
        else:
            return self.PROJECT_CONFIGS[default_project]

    # def _print_current_config(self):
    #     """打印当前配置"""
    #     print("=" * 50)
    #     print("当前测试配置:")
    #     print(f"环境: {self.ENV}")
    #     print(f"测试项目：{self.project_name}")
    #     print(f"测试用例文件: {self.TESTCASES}")
    #     print(f"元素定位器文件: {self.ELEMENT_LOCATORS}")
    #     print(f"基础URL: {self.URL}")
    #     print(f"浏览器: {self.BROWSER}, 无头模式: {self.HEADLESS}")
    #     print(f"数据库配置: 服务器:{self.DB_HOST},端口:{self.DB_PORT},用户名:{self.DB_USER},库:{self.DB_NAME}")
    #     print("=" * 50)

settings = Settings()

# ============ 敏感配置启动校验（进程启动时执行一次） ============
REQUIRED_ENV = [
    ("LOGIN_USER", "登录账号"),
    ("PASSWORD", "登录密码"),
    ("DB_HOST", "数据库地址"),
    ("DB_USER", "数据库用户"),
    ("DB_PASSWORD", "数据库密码"),
    ("DB_NAME", "数据库名"),
]
missing = [cn for cn, _ in REQUIRED_ENV if not getattr(settings, cn, "")]
if missing:
    descs = "、".join(f"{cn}({desc})" for cn, desc in REQUIRED_ENV if not getattr(settings, cn, ""))
    # 只有真正要跑 UI 用例集时才中断，跑接口用例集时不阻塞
    if os.getenv("TEST_SUITE", "") in ("ui", "all"):
        raise SystemExit(f"[配置错误] 以下敏感配置未设置(请通过环境变量或 .env 提供): {descs}")
    print(f"[配置提示] 以下 UI 敏感配置未设置: {descs}")

