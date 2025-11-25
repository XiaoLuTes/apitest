import logging
import os
from datetime import datetime
from config.setting import setting


def setup_logger():
    # 创建日志目录
    log_dir = os.path.join(setting.REPORT_PATH, "../../api/reports/logs")
    os.makedirs(log_dir, exist_ok=True)

    # 创建日志文件名（带时间戳）
    log_file = os.path.join(log_dir, f"API_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")

    # 配置日志系统
    logger = logging.getLogger("API_Automation")
    logger.setLevel(logging.INFO)

    # 创建文件处理器
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)

    # 创建控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)

    # 创建格式化器
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    # 添加处理器到日志器
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    # 示例日志输出
    logger.info("Logger initialized successfully")

    return logger


logger = setup_logger()
