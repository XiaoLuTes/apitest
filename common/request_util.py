import requests

session = requests.session()
def send_request(method, url, data, **kwargs):
    req = None
    str(method).lower()
    if method == 'get':
        req = session.request(method=method, url=url, params=data, **kwargs)
    elif method == 'post':
        req = session.request(method=method, url=url, json=data, **kwargs)
    else:
        pass
    return req
