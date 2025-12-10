import logging
import os
from datetime import datetime
from config.setting import setting


def setup_logger():
    # 创建日志目录（复用原有逻辑）
    log_dir = os.path.join(setting.REPORT_PATH, "../../api/reports/logs")
    log_dir_error = os.path.join(setting.REPORT_PATH, "../../api/reports/logs_error")
    os.makedirs(log_dir, exist_ok=True)
    os.makedirs(log_dir_error, exist_ok=True)

    # 1. 原有全量日志文件（保留）
    full_log_file = os.path.join(log_dir, f"API_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
    # 2. 新增error/warning专属日志文件（命名区分）
    error_log_file = os.path.join(log_dir_error, f"API_error_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")

    # 配置核心日志器（保持原有名称，避免冲突）
    logger = logging.getLogger("API_Automation")
    logger.setLevel(logging.DEBUG)  # 根日志器级别需低于所有处理器，确保能接收所有日志
    logger.handlers.clear()  # 清空重复处理器（避免多次调用setup_logger时重复添加）

    # 1. 全量文件处理器（DEBUG及以上，保留所有日志）
    file_handler = logging.FileHandler(full_log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    # 2. 控制台处理器（INFO及以上，保留原有逻辑）
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)

    # ---------------------仅Warning/Error级别日志---------------------
    error_file_handler = logging.FileHandler(error_log_file, encoding="utf-8")
    error_file_handler.setLevel(logging.WARNING)  # 仅处理WARNING/ERROR/CRITICAL

    # 统一日志格式（可给error日志单独定制格式，比如增加错误堆栈）
    basic_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    # （可选）给error日志添加更详细的格式（比如包含异常堆栈）
    error_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'
    )

    # 绑定格式器
    file_handler.setFormatter(basic_formatter)
    console_handler.setFormatter(basic_formatter)
    error_file_handler.setFormatter(error_formatter)  # error日志用详细格式

    # 添加所有处理器到日志器
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    logger.addHandler(error_file_handler)

    # 示例日志（验证效果）
    logger.info("Logger initialized successfully")

    return logger


logger = setup_logger()
