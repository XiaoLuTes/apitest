import os


class Setting:
    def __init__(self):
        self.ENV = self._get_env_var("ENV", "测试环境")
        self.TEST_FLIELOAD = f"testcase/cloud_test.xlsx"  # excel测试用例路径
        self.TEST_FLIELOAD_YAML = f"testcase/test_yl.yaml"  # yaml测试用例路径
        self.EXTRACTFILE = f"variable/extract.yaml"  # 临时变量文件路径
        self.ALL_YAML = f"variable/all.yaml"  # 全局变量文件路径
        self.REPORT_PATH = self._get_env_var("REPORT_PATH", "reports/")  # 报告路径
        self.BASE_URLS = {
            "生产环境": "https://admin.gsrtech.com",
            "预生产环境": "https://stage-admin.gsrtech.com/",
            "测试环境": "https://test-admin.gsrtech.com/"
        }
        self.TEST_URL = self.BASE_URLS[self.ENV]

    @staticmethod
    def _get_env_var(var_name: str, default: str) -> str:
        """从环境变量获取配置，如果没有则使用默认值"""
        return os.getenv(var_name, default)


setting = Setting()
