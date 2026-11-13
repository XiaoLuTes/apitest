"""通用重试：把“失败后隔一会儿再试”的逻辑从执行器里独立出来"""
import time

from config.setting import setting
from common.logger import logger


def resolve(value):
    """解析 retry 列的原始值，返回 (最多尝试次数, 每次间隔秒数)"""
    default_times = max(1, int(setting.HTTP_RETRY_TIMES))  # 重试次数
    default_interval = max(0.0, float(setting.HTTP_RETRY_INTERVAL))  # 重试间隔S

    if value is None or (isinstance(value, str) and not value.strip()):
        return default_times, default_interval

    if isinstance(value, dict):
        times = int(value.get('times', default_times))
        interval = float(value.get('interval', default_interval))
        return max(1, times), max(0.0, interval)

    try:
        times = int(float(str(value).strip()))
    except (TypeError, ValueError):
        raise ValueError(
            f"retry 列取值无法识别：[{value}]，可写次数（如 5）或 {{\"times\": 20, \"interval\": 2}}"
        ) from None
    return max(1, times), default_interval


def call(func, times=None, interval=None, retry_on=(AssertionError,), desc=""):
    """重复执行 func，直到成功或达到最大次数

    :param func: 无参可调用对象；抛出 retry_on 中的异常视为可重试
    :param times: 最多尝试次数（含第一次），默认取 setting.HTTP_RETRY_TIMES
    :param interval: 两次尝试之间的等待秒数，默认取 setting.HTTP_RETRY_INTERVAL
    :param retry_on: 视为可重试的异常类型
    :param desc: 日志描述，如“用例 12”
    :return: func 的返回值
    """
    times = max(1, int(times if times is not None else setting.HTTP_RETRY_TIMES))
    interval = max(0.0, float(interval if interval is not None else setting.HTTP_RETRY_INTERVAL))

    for attempt in range(1, times + 1):
        try:
            result = func()
        except retry_on as error:
            if attempt >= times:
                logger.error(f"{desc} 第 {attempt}/{times} 次失败，不再重试：{error}")
                raise
            logger.warning(f"{desc} 第 {attempt}/{times} 次未通过，{interval}s 后重试：{error}")
            time.sleep(interval)
            continue
        if times > 1:
            logger.info(f"{desc} 第 {attempt}/{times} 次尝试通过")
        return result
    return None
