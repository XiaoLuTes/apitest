import requests

session = requests.session()
def send_request(method, url, data, **kwargs):
    str(method).lower()
    if method == 'get':
        req = session.request(method=method, url=url, params=data, **kwargs)
    elif method == 'post':
        req = session.request(method=method, url=url, json=data, **kwargs)
    elif method == 'put':
        req = session.request(method=method, url=url, json=data, **kwargs)
    elif method == 'patch':
        req = session.request(method=method, url=url, json=data, **kwargs)
    elif method == 'delete':
        # DELETE 请求通常不需要请求体，但有些API可能需要
        if data:
            req = session.request(method=method, url=url, json=data, **kwargs)
        else:
            req = session.request(method=method, url=url, **kwargs)
    elif method == 'head':
        req = session.request(method=method, url=url, **kwargs)
    elif method == 'options':
        req = session.request(method=method, url=url, **kwargs)
    else:
        # 对于不支持的请求方法，直接使用原始方式
        req = session.request(method=method, url=url, data=data, **kwargs)
    return req
