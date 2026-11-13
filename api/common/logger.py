"""接口用例集日志：统一走 core.logger，输出到 <root>/reports/logs/API_log_<日期>.log"""
from core.logger import setup_logger

logger = setup_logger("API_Automation", "API")
