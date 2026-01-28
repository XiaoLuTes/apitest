import logging
import os
from datetime import datetime
from logging.handlers import RotatingFileHandler  # 新增：按大小切割日志


def setup_logger():
    # 1. 规范日志目录路径（使用绝对路径，避免相对路径陷阱）
    # 获取当前文件所在目录，拼接日志目录（更稳定）
    current_dir = os.path.dirname(os.path.abspath(__file__))
    log_dir = os.path.join(current_dir, "..", "reports", "logs")
    log_dir_error = os.path.join(current_dir, "..", "reports", "logs_error")
    # 确保目录存在（兼容所有系统）
    os.makedirs(log_dir, exist_ok=True)
    os.makedirs(log_dir_error, exist_ok=True)
    # 转为绝对路径（消除..的影响）
    log_dir = os.path.abspath(log_dir)
    log_dir_error = os.path.abspath(log_dir_error)

    # 2. 日志文件名优化（按日期命名，而非时间戳，避免文件过多）
    today = datetime.now().strftime("%Y%m%d")
    full_log_file = os.path.join(log_dir, f"API_log_{today}.log")
    error_log_file = os.path.join(log_dir_error, f"API_error_log_{today}.log")

    # 3. 获取/创建日志器（单例模式，避免重复添加处理器）
    logger = logging.getLogger("API_Automation")
    logger.setLevel(logging.DEBUG)  # 根级别必须最低，确保所有日志都能被处理器接收
    logger.propagate = False  # 防止日志传递到根日志器，导致重复输出

    # 清空已有处理器（关键：避免多次调用setup_logger时重复添加）
    if logger.handlers:
        logger.handlers.clear()

    # 4. 定义日志格式
    # 基础格式（全量日志）
    basic_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'
    )
    # 错误日志格式（包含异常堆栈）
    error_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(funcName)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # 5. 全量日志处理器（按大小切割，避免文件过大）
    # 单个文件最大50MB，最多保留5个备份
    file_handler = RotatingFileHandler(
        full_log_file,
        mode='a',
        maxBytes=50 * 1024 * 1024,  # 50MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(basic_formatter)

    # 6. 控制台处理器（只输出INFO及以上）
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(basic_formatter)

    # 7. 错误日志处理器（只输出ERROR及以上，按大小切割）
    error_file_handler = RotatingFileHandler(
        error_log_file,
        mode='a',
        maxBytes=50 * 1024 * 1024,
        backupCount=5,
        encoding='utf-8'
    )
    error_file_handler.setLevel(logging.ERROR)  # 仅记录ERROR/CRITICAL
    error_file_handler.setFormatter(error_formatter)

    # 8. 添加所有处理器
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    logger.addHandler(error_file_handler)

    return logger


# 单例模式初始化（确保全局只有一个logger实例）
logger = setup_logger()
