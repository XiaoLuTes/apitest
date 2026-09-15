import requests

from config.setting import setting
from common.logger import logger

session = requests.session()


def send_request(method, url, data, **kwargs):
    """按请求方法发送接口请求

    :param method: 请求方法，大小写不敏感（get/post/put/patch/delete/head/options）
    :param url: 完整请求地址
    :param data: get 作为查询参数，其余方法作为 json 请求体
    :param kwargs: 透传给 requests 的其他参数（如 headers）；未传 timeout 时使用 setting.HTTP_TIMEOUT
    :return: requests.Response 对象
    """
    method = str(method).strip().lower()
    # 未显式指定超时时使用配置中的默认超时：setting.HTTP_TIMEOUT
    kwargs.setdefault('timeout', setting.HTTP_TIMEOUT)

    try:
        if method == 'get':
            req = session.request(method=method, url=url, params=data, **kwargs)
        elif method in ('post', 'put', 'patch'):
            req = session.request(method=method, url=url, json=data, **kwargs)
        elif method == 'delete':
            # DELETE 请求通常不需要请求体，但有些API可能需要
            if data:
                req = session.request(method=method, url=url, json=data, **kwargs)
            else:
                req = session.request(method=method, url=url, **kwargs)
        elif method in ('head', 'options'):
            req = session.request(method=method, url=url, **kwargs)
        else:
            # 对于不支持的请求方法，直接使用原始方式
            req = session.request(method=method, url=url, data=data, **kwargs)
    except requests.RequestException as e:
        # 统一封装网络层异常，失败时能直接看出是哪个请求出的问题
        logger.error(f"请求发送失败 [{method} {url}]: {e}")
        raise RuntimeError(f"请求发送失败 [{method} {url}]: {e}") from e
    return req
