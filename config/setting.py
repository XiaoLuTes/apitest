import os


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
        self.BASE_URLS = {
            "生产环境": "https://admin.gsrtech.com",
            "预生产环境": "https://stage-admin.gsrtech.com",
            "测试环境": "https://test-omni.gsrtech.com"
        }
        self.TEST_URL = self.BASE_URLS[self.ENV]

        # 数据库配置
        self.DB_HOST_LIST = {
            "测试环境": "43.154.110.127",
            "预生产环境": "",
            "生产环境": ""
        }
        self.DB_USER_LIST = {
            "测试环境": "gsr_db",
            "预生产环境": "",
            "生产环境": ""
        }
        self.DB_PASSWORD_LIST = {
            "测试环境": "gsr666666",
            "预生产环境": "",
            "生产环境": ""
        }
        self.DB_PORT_LIST = {
            "测试环境": "3306",
            "预生产环境": "",
            "生产环境": ""
        }
        self.DB_NAME_LIST = {
            "测试环境": "gsr",
            "预生产环境": "",
            "生产环境": ""
        }
        self.DB_HOST = self._get_env_var("DB_HOST", self.DB_HOST_LIST[self.ENV])
        self.DB_USER = self._get_env_var("DB_USER", self.DB_USER_LIST[self.ENV])
        self.DB_PASSWORD = self._get_env_var("DB_PASSWORD", self.DB_PASSWORD_LIST[self.ENV])
        self.DB_PORT = self._get_env_var("DB_PORT", self.DB_PORT_LIST[self.ENV])
        self.DB_NAME = self._get_env_var("DB_NAME", self.DB_NAME_LIST[self.ENV])
        self.DB_TIMEOUT = int(self._get_env_var("DB_TIMEOUT", "30"))

    @staticmethod
    def _get_env_var(var_name: str, default: str) -> str:
        """从环境变量获取配置，如果没有则使用默认值"""
        return os.getenv(var_name, default)


setting = Setting()
