# -*- coding: utf-8 -*-
"""业务平台 token 预检

解决的问题：`ACCESS_TOKEN_ADMIN`（浏览器 GSR-Token）约 2 小时过期，过期后跑用例会在
中途报 401/110106，容易被误判成"接口缺陷"。执行前先花 1 秒探一下，过期就立刻提示用户更新。

用法：
    from core.token_check import check_admin_token
    ok, detail = check_admin_token("https://test-admin.gsrtech.com", token)
"""
import requests


def check_admin_token(base_url: str, token: str, timeout: int = 10):
    """返回 (ok, detail)

    ok: True 有效 / False 无效 / None 网络异常（无法判定）
    """
    if not token:
        return False, "未配置 ACCESS_TOKEN_ADMIN"
    if not base_url:
        return None, "未配置业务平台地址"

    url = base_url.rstrip("/") + "/api/center/payrollSalaryPackage/list"
    try:
        resp = requests.get(url, params={"pageSize": 1, "pageNum": 1},
                            headers={"Authorization": "Bearer " + token}, timeout=timeout)
    except Exception as e:                     # noqa: BLE001
        return None, "网络异常：%s" % e

    try:
        body = resp.json()
    except Exception:                          # noqa: BLE001
        return False, "HTTP %s 非 JSON 响应（可能被网关拦截）" % resp.status_code

    code = body.get("code")
    msg = body.get("msg") or ""
    if resp.status_code == 200 and code in (200, None):
        return True, "HTTP 200，token 有效"
    if code == 110106:
        return False, "code=110106 没有访问权限（token 失效或权限缓存未刷新）"
    if resp.status_code == 401:
        return False, "HTTP 401 令牌无效或已过期"
    return False, "HTTP %s code=%s msg=%s" % (resp.status_code, code, msg)


TOKEN_HELP = """请更新 .env 的 ACCESS_TOKEN_ADMIN：
  1. 浏览器登录 {url} → F12 → Application/存储 → Cookies → 复制 GSR-Token 的值
  2. 粘贴到 D:\\lu\\pycharm\\autotest\\.env 的 ACCESS_TOKEN_ADMIN=
  3. 再执行：python run.py check-token
（该 token 约 2 小时过期；UI 免扫码登录与接口 Authorization 用的是同一个）"""
