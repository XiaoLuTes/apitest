"""统一日志工厂

api 与 ui 共用同一套日志实现，只是 logger 名称与文件名前缀不同：
    reports/logs/API_log_20261113.log  /  reports/logs_error/API_error_log_20261113.log
    reports/logs/UI_log_20261113.log   /  reports/logs_error/UI_error_log_20261113.log
"""
import logging
import os
import time
from datetime import datetime
from logging.handlers import RotatingFileHandler  # 按大小切割日志

from core import paths


def cleanup_old_logs(log_dir, days=7):
    """清理 N 天前的日志，但始终保留最新的一份（即使它已超过 N 天）"""
    cutoff = time.time() - days * 86400
    if not os.path.isdir(log_dir):
        return
    files = [os.path.join(log_dir, f) for f in os.listdir(log_dir)
             if os.path.isfile(os.path.join(log_dir, f))]
    if not files:
        return
    newest = max(files, key=os.path.getmtime)
    removed = 0
    for path in files:
        if path != newest and os.path.getmtime(path) < cutoff:
            os.remove(path)
            removed += 1
    if removed:
        print(f"[logger] 已清理 {removed} 个过期日志文件: {log_dir}")


def setup_logger(logger_name, prefix, log_dir=None, error_dir=None):
    """创建/重建 logger（单例，避免重复添加处理器）

    :param logger_name: logger 名称，如 API_Automation / UI_Automation
    :param prefix: 日志文件名前缀，如 API / UI
    :param log_dir: 全量日志目录，默认 <root>/reports/logs
    :param error_dir: 错误日志目录，默认 <root>/reports/logs_error
    """
    log_dir = log_dir or paths.LOGS
    error_dir = error_dir or paths.LOGS_ERROR
    os.makedirs(log_dir, exist_ok=True)
    os.makedirs(error_dir, exist_ok=True)
    cleanup_old_logs(log_dir, days=7)        # 全量日志
    cleanup_old_logs(error_dir, days=7)      # 错误日志

    today = datetime.now().strftime("%Y%m%d")
    full_log_file = os.path.join(log_dir, f"{prefix}_log_{today}.log")
    error_log_file = os.path.join(error_dir, f"{prefix}_error_log_{today}.log")

    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.DEBUG)  # 根级别必须最低，确保所有日志都能被处理器接收
    logger.propagate = False        # 防止日志传递到根日志器，导致重复输出
    if logger.handlers:
        logger.handlers.clear()

    basic_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'
    )
    error_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(funcName)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    file_handler = RotatingFileHandler(full_log_file, mode='a',
                                       maxBytes=50 * 1024 * 1024, backupCount=5, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(basic_formatter)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(basic_formatter)

    error_file_handler = RotatingFileHandler(error_log_file, mode='a',
                                             maxBytes=50 * 1024 * 1024, backupCount=5, encoding='utf-8')
    error_file_handler.setLevel(logging.ERROR)
    error_file_handler.setFormatter(error_formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    logger.addHandler(error_file_handler)
    return logger
