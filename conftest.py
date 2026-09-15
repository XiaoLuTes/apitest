import os

import pytest
from config.setting import setting
from common import allure_util, excel_read, run_state, wecom, yaml_util
from common.logger import logger
from common.database import DatabaseUtils


@pytest.fixture(scope="session", autouse=True)   # autouse=True  自动执行
def execute_session():
    logger.info("=========================== 接口测试开始 ===========================")
    run_state.reset()
    yaml_util.clean_yaml()
    yaml_util.write_yaml(yaml_util.read_yaml_all())
    # 把 .env 里的敏感配置注入成运行期变量（用例里可用 ${user_token} 这种方式引用）
    _env_vars = {key: value for key, value in setting.ENV_VARIABLES.items() if value}
    if _env_vars:
        yaml_util.write_yaml(_env_vars)
        logger.info(f"已注入环境变量：{list(_env_vars.keys())}")
    db_instance = DatabaseUtils()
    try:
        yield
    finally:
        # 1、把缓存的执行结果写入结果文件（源用例文件不再被修改）；2、关闭会话级数据库连接
        result_files = excel_read.Excel.save_results()
        # 把结果文件作为附件附加到 allure 报告（报告里会出现一条可下载的汇总记录）
        allure_util.export_result_files(result_files, title=f"用例执行结果文件（{run_state.summary_text()}）")
        logger.info(f"本次执行汇总：{run_state.summary_text()}")
        # 企业微信通知：在 .env / 系统环境变量里配置 WECOM_WEBHOOK 后，会话结束自动推送执行结果
        build_url = os.environ.get("BUILD_URL")   # Jenkins 会注入构建地址，本地执行时为 None
        wecom.notify(
            setting.WECOM_WEBHOOK,
            project=setting.CURRENT_PROJECT,
            summary=run_state.summary_text(),
            failed_cases=[f"{case_id}-{name}" for case_id, name in run_state.failed_cases()],
            result_files=result_files,
            report_url=f"{build_url}allure/" if build_url else None,
        )
        # 把结果文件（源用例的完整副本）也发到群里：企微文件消息上限 20MB，上传失败只记 WARNING
        if result_files:
            wecom.send_file(setting.WECOM_WEBHOOK, result_files[0])
        if db_instance.connection is not None:
            db_instance.close_database_connection()
            logger.info(f"测试结束，关闭数据库链接")
        else:
            logger.info(f"无数据库操作，无需关闭数据库链接")
        logger.info("=========================== 接口测试结束 ===========================\n")
