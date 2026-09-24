import os

import requests

from config.setting import setting
from common.logger import logger

session = requests.session()


def send_request(method, url, data, **kwargs):
    """按请求方法发送接口请求

    :param method: 请求方法，大小写不敏感（get/post/put/patch/delete/head/options/upload；
           upload 可用 upload:put、upload:patch 指定动词）
    :param url: 完整请求地址
    :param data: get 作为查询参数，其余方法作为 json 请求体；
           method 为 upload 时，data 为本地文件路径，或
           {"file": 路径, "file_field": 服务端字段名, "其余键": 表单字段值}；
           相对路径以项目根目录（setting.BASE_DIR）为基准，executor 已完成变量替换
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
        elif method.split(':', 1)[0].strip() == 'upload':
            # 文件上传：data 为文件路径，或 {"file": 路径, "file_field": 服务端字段名, "其余键": 表单字段值}
            upload_verb = 'post'
            if ':' in method:
                upload_verb = method.split(':', 1)[1].strip() or 'post'
                if upload_verb not in ('post', 'put', 'patch'):
                    raise ValueError(
                        f"upload 的动词只支持 post/put/patch，当前为 [upload:{upload_verb}]，请检查用例 method 列"
                    )
            file_field = 'file'
            form_data = None
            if isinstance(data, dict):
                if not str(data.get('file') or '').strip():
                    raise ValueError(
                        f"upload 用例的 data 为 JSON 时必须包含非空的 file 键，当前键为 {list(data.keys())}，"
                        f"请检查用例"
                    )
                file_field = str(data.get('file_field') or '').strip() or 'file'
                form_data = {k: v for k, v in data.items() if k not in ('file', 'file_field')} or None
                for field_name, field_value in (form_data or {}).items():
                    if field_value is None or isinstance(field_value, (dict, list, tuple, set)):
                        raise ValueError(
                            f"upload 表单字段 [{field_name}] 的值只支持字符串/数字，当前为 [{field_value}]，"
                            f"请检查用例"
                        )
                file_path = str(data['file']).strip()
            elif isinstance(data, str) and data.strip():
                file_path = data.strip()
            else:
                raise ValueError(
                    f"upload 用例的 data 列应为文件路径，或形如 "
                    f'{{"file": "路径", "file_field": "服务端字段名", "其他表单字段": "值"}}，'
                    f"当前为 [{data}]，请检查用例"
                )
            if not os.path.isabs(file_path):
                file_path = os.path.join(setting.BASE_DIR, file_path)
            try:
                f = open(file_path, 'rb')
            except OSError as e:
                raise ValueError(f"上传文件不存在或无法读取 [{file_path}]: {e}") from e
            headers = kwargs.get('headers')
            if headers:
                kwargs['headers'] = {k: v for k, v in headers.items() if str(k).lower() != 'content-type'}
            with f:
                req = session.request(method=upload_verb, url=url, data=form_data,
                                      files={file_field: (os.path.basename(file_path), f)}, **kwargs)
        else:
            raise ValueError(
                f"不支持的请求方法 [{method}]，当前支持：get/post/put/patch/delete/head/options/upload"
                f"（upload 可用 upload:put、upload:patch 指定动词），"
                f"请检查用例 method 列拼写（db_select/db_update 由执行器单独分流）"
            )
    except requests.RequestException as e:
        # 统一封装网络层异常，失败时能直接看出是哪个请求出的问题
        logger.error(f"请求发送失败 [{method} {url}]: {e}")
        raise RuntimeError(f"请求发送失败 [{method} {url}]: {e}") from e
    return req
