import os

from core import paths
from core.env import load_env

# 仓库根目录：autotest/
# 接口用例集目录：autotest/api/（本文件位于 api/config/setting.py）
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 统一从仓库根目录的 .env 读取（系统环境变量优先，不会被 .env 覆盖）
load_env()


class Setting:
    def __init__(self):
        self.ENV = self._get_env_var("ENV", "测试环境")
        self.BASE_DIR = BASE_DIR
        # key = 项目名（CURRENT_PROJECT 用），value = 用例文件（相对 api/ 或绝对路径）
        self.TEST_FLIELOADS = {
            "假勤": "testcase/test_approval.xlsx",
            "调试": "testcase/test_test.xlsx",
            "payroll": "testcase/test_payroll.xlsx",
            "审批流或签自动通过": "testcase/test_approval_auto_approved.xlsx",
            "审批流或签矩阵": "testcase/test_approval_ouqian_matrix.xlsx",
            "报销自动审批": "testcase/test_reimbursement_auto_approval.xlsx",
            "报销审批人为空": "testcase/test_reimbursement_empty_approver.xlsx",
            "假勤审批人为空": "testcase/test_leave_empty_approver.xlsx",
            "审批流员工标签": "testcase/test_approval_employee_tag.xlsx",
            "薪资包结算": "testcase/test_payroll_salary_package_offcycle.xlsx",
            "薪资包管理查询": "testcase/test_payroll_package_query.xlsx",
        }
        # 项目名解析优先级：API_PROJECT > CURRENT_PROJECT
        # （CURRENT_PROJECT 是 UI 项目名时接口侧忽略，方便两个用例集共用一个 .env）
        self.CURRENT_PROJECT = os.getenv("API_PROJECT") or self._get_env_var("CURRENT_PROJECT", '')
        if self.CURRENT_PROJECT and self.CURRENT_PROJECT not in self.TEST_FLIELOADS:
            if os.getenv("API_PROJECT"):
                raise SystemExit(
                    "[配置错误] API_PROJECT=%r 不是接口用例集，可选值：%s"
                    % (self.CURRENT_PROJECT, "、".join(self.TEST_FLIELOADS))
                )
            self.CURRENT_PROJECT = ""
        if not self.CURRENT_PROJECT and os.getenv("TEST_SUITE", "") in ("api", "all"):
            raise SystemExit(
                "[配置错误] 未指定接口用例项目，请执行 python run.py api <项目名>，"
                "或设置 API_PROJECT。可选值：%s" % "、".join(self.TEST_FLIELOADS)
            )
        # excel测试用例路径（绝对路径，不依赖运行目录）
        self.TEST_FLIELOAD = paths.resolve(self.TEST_FLIELOADS[self.CURRENT_PROJECT], BASE_DIR) \
            if self.CURRENT_PROJECT else ""
        self.TEST_FLIELOAD_YAML = paths.resolve("testcase/test_yl.yaml", BASE_DIR)  # yaml测试用例路径
        self.EXTRACTFILE = paths.resolve("variable/extract.yaml", BASE_DIR)  # 临时变量文件路径
        self.ALL_YAML_ENV = {
            "生产环境": "variable/all_pro.yaml",
            "预生产环境": "variable/all_prepro.yaml",
            "测试环境": "variable/all.yaml"
        }
        # 全局变量文件路径
        self.ALL_YAML = paths.resolve(self.ALL_YAML_ENV[self.ENV], BASE_DIR)
        # 报告与产物目录（统一在仓库根目录 reports/ 下，与 UI 用例集共用目录结构）
        self.REPORT_PATH = self._get_env_var("REPORT_PATH", paths.REPORTS)
        # 用例执行结果输出目录：结果文件 = 源用例文件的完整副本 + 本次执行的 result 列
        self.RESULT_PATH = self._get_env_var("RESULT_PATH", paths.RESULTS_API)
        # allure 原始结果目录（与 pytest.ini 里的 --alluredir 保持一致）
        self.ALLURE_RESULT_PATH = self._get_env_var("ALLURE_RESULT_PATH", paths.ALLURE_RESULTS)
        # 下载文件保存目录（下载接口落盘的位置）
        self.DOWNLOAD_PATH = self._get_env_var("DOWNLOAD_PATH", paths.DOWNLOADS)
        # 失败重试默认值（用例 retry 列留空时使用）
        self.HTTP_RETRY_TIMES = int(self._get_env_var("HTTP_RETRY_TIMES", 1))
        self.HTTP_RETRY_INTERVAL = float(self._get_env_var("HTTP_RETRY_INTERVAL", 1))
        # 企业微信群机器人 Webhook：配置后会话结束自动推送执行结果卡片（留空则不发送，本地执行无感）
        self.WECOM_WEBHOOK = self._get_env_var("WECOM_WEBHOOK", "")
        # 企业微信通知：markdown 内容上限（字节，企微硬性上限 4096）与请求超时（秒）
        self.WECOM_MAX_CONTENT_BYTES = int(self._get_env_var("WECOM_MAX_CONTENT_BYTES", "4000"))
        self.WECOM_TIMEOUT = int(self._get_env_var("WECOM_TIMEOUT", "10"))
        # 企业微信通知总开关：false 时即使配了 Webhook 也不推送（本地调试不想打扰群时用）
        self.WECOM_ENABLE = self._get_env_var("WECOM_ENABLE", "true").strip().lower() in (
            "true", "1", "yes", "y", "on")
        self.BASE_URLS = {
            "生产环境": {
                "管理端": "https://admin.gsrtech.com",
                "员工端": "https://admin.gsrtech.com"
            },
            "预生产环境": {
                "管理端": "https://stage-admin.gsrtech.com",
                "员工端": "https://stage-admin.gsrtech.com"
            },
            "测试环境": {
                "管理端": "https://test-admin.gsrtech.com",
                "员工端": "https://test-omni.gsrtech.com"
            }
        }
        self.TEST_URL = self.BASE_URLS[self.ENV]
        self.DEFAULT_URL = '管理端'
        # 接口请求默认超时（秒），可通过环境变量 HTTP_TIMEOUT 覆盖
        self.HTTP_TIMEOUT = int(self._get_env_var("HTTP_TIMEOUT", "30"))

        # 用例失败时，是否把它 extract 出来的变量也判定为不可信（依赖这些变量的下游用例会自动 skip）
        # True（默认）：断言失败也视为“产出的数据不可信”；False：只有“没取到响应 / 提取失败”才连带跳过下游
        # 可用环境变量 INVALIDATE_ON_ANY_FAILURE 覆盖（true/1/yes/on 视为 True）
        self.INVALIDATE_ON_ANY_FAILURE = self._get_env_var("INVALIDATE_ON_ANY_FAILURE", "True").strip().lower() in (
            "true", "1", "yes", "y", "on")

        # 数据库配置
        # 优先级：系统环境变量 > .env > 这里的默认值
        self.DB_HOST = self._get_env_var("DB_HOST", '')
        self.DB_USER = self._get_env_var("DB_USER", '')
        self.DB_PASSWORD = self._get_env_var("DB_PASSWORD", '')
        self.DB_PORT = self._get_env_var("DB_PORT", '')
        self.DB_NAME = self._get_env_var("DB_NAME", '')
        self.DB_TIMEOUT = int(self._get_env_var("DB_TIMEOUT", "30"))

        # 需要从 .env / 环境变量注入成运行期变量的敏感配置（值取自同名环境变量，通常写在 .env 里）
        # 会话开始时会写入 variable/extract.yaml，用例里可直接用 ${键名} 引用
        # 例如 all.yaml 里 headers_user 用的就是 ${user_token}
        self.ENV_VARIABLES = {
            "user_token": self._get_env_var("USER_TOKEN", ""),
            "access_token_admin": self._get_env_var("ACCESS_TOKEN_ADMIN", ""),
        }

    @staticmethod
    def _get_env_var(var_name: str, default: str) -> str:
        """从环境变量获取配置，如果没有则使用默认值"""
        return os.getenv(var_name, default)


setting = Setting()
