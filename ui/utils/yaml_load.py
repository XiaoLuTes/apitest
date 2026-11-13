import os
import time
from ui.utils.logger import logger
from ui.config.settings import settings
from ui.utils.common import read_yaml, write_yaml


class YamlLoad:
    _batch_id = None  # 类级共享：同一进程内所有实例复用同一批次号

    def __init__(self):
        self.setting = settings
        # 首次创建时生成批次号，后续实例复用
        if YamlLoad._batch_id is None:
            YamlLoad._batch_id = time.strftime("%Y%m%d_%H%M%S")
        self.batch_id = YamlLoad._batch_id

    def load_test_cases(self):
        """加载测试用例"""
        file_path = self.setting.TESTCASES
        try:
            data = read_yaml(file_path)
            test_cases = data.get('test_cases', [])
            logger.info(f"测试用例地址：{file_path}")
            logger.info(f"从YAML文件加载了 {len(test_cases)} 个测试用例")
            return test_cases
        except Exception as e:
            logger.error(f"加载测试用例失败: {str(e)}")
            return []

    def _get_result_file_path(self):
        """结果文件路径：reports/test_results/<用例名>_<批次号>.yaml"""
        case_name = os.path.splitext(os.path.basename(self.setting.TESTCASES))[0]
        result_dir = self.setting.TEST_RESULT_DIR
        os.makedirs(result_dir, exist_ok=True)
        return os.path.join(result_dir, f"{case_name}_{self.batch_id}.yaml")

    def update_test_result(self, test_case_id, result):
        """更新测试用例结果（写入 reports/test_results，源用例文件保持只读）"""
        result_file = self._get_result_file_path()
        try:
            if os.path.exists(result_file):
                data = read_yaml(result_file)
            else:
                # 首次写入：从源用例文件拷贝骨架（只保留 id/name）
                source_data = read_yaml(self.setting.TESTCASES)
                data = {
                    "source": self.setting.TESTCASES,          # 溯源：来自哪个用例文件
                    "run_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "test_cases": [
                        {"id": tc.get("id"), "name": tc.get("name"), "result": ""}
                        for tc in source_data.get("test_cases", [])
                    ]
                }

            for test_case in data["test_cases"]:
                if test_case["id"] == test_case_id:
                    test_case["result"] = result
                    test_case["update_time"] = time.strftime("%Y-%m-%d %H:%M:%S")
                    break

            write_yaml(result_file, data)
            logger.info(f"测试结果已写入: {result_file} | 用例 {test_case_id} => {result}")
            return True
        except Exception as e:
            logger.error(f"更新测试结果失败: {str(e)}")
            return False
