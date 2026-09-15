import os


def _load_dotenv(path: str) -> None:
    """极简 .env 加载器（不引入额外依赖）

    规则：KEY=VALUE，# 开头为注释，空行忽略，值两端引号会被去掉；
    已经存在的系统环境变量优先，不会被 .env 覆盖（便于 Jenkins / CI 用环境变量注入）。
    """
    if not os.path.isfile(path):
        return
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key:
                    os.environ.setdefault(key, value)
    except OSError:
        pass


# 项目根目录下的 .env（与 config/ 同级）；Jenkins 等 CI 也可以直接用系统环境变量
_load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))


class Setting:
    def __init__(self):
        self.ENV = self._get_env_var("ENV", "测试环境")
        self.TEST_FLIELOADS = {
            "假勤": f"testcase/test_approval.xlsx",
            "调试": f"testcase/test_test.xlsx"
        }
        self.CURRENT_PROJECT = self._get_env_var("CURRENT_PROJECT", '假勤')
        self.TEST_FLIELOAD = self.TEST_FLIELOADS[self.CURRENT_PROJECT]  # excel测试用例路径
        self.TEST_FLIELOAD_YAML = f"testcase/test_yl.yaml"  # yaml测试用例路径
        self.EXTRACTFILE = f"variable/extract.yaml"  # 临时变量文件路径
        self.ALL_YAML_ENV = {
            "生产环境": f"variable/all_pro.yaml",
            "预生产环境": f"variable/all_prepro.yaml",
            "测试环境": f"variable/all.yaml"
        }
        self.ALL_YAML = self.ALL_YAML_ENV[self.ENV]  # 全局变量文件路径
        self.REPORT_PATH = self._get_env_var("REPORT_PATH", "reports/")  # 报告路径
        # 用例执行结果输出目录：结果文件 = 源用例文件的完整副本 + 本次执行的 result 列
        self.RESULT_PATH = self._get_env_var("RESULT_PATH", f"{self.REPORT_PATH}results/")
        # allure 原始结果目录（与 pytest.ini 里的 --alluredir 保持一致）
        self.ALLURE_RESULT_PATH = self._get_env_var("ALLURE_RESULT_PATH", f"{self.REPORT_PATH}temp/")
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
                "员工端": "https://test-admin.gsrtech.com"
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
        # 数据库配置：敏感信息不写进代码，真实值放在项目根目录的 .env 里
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
        }

    @staticmethod
    def _get_env_var(var_name: str, default: str) -> str:
        """从环境变量获取配置，如果没有则使用默认值"""
        return os.getenv(var_name, default)


setting = Setting()
