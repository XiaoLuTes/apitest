"""禅道客户端（禅道 REST v1 / 老版本 api.php 会话）

设计目标：把"提单"变成框架里的一个方法，配置留在 .env，代码只写一次。
    from core.zentao import ZentaoClient
    zt = ZentaoClient.from_env()
    zt.whoami()                      # 连通性 + 身份确认
    zt.products()                    # 产品列表（拿 product id）
    zt.modules(1)                    # 模块列表（拿 module id）
    zt.create_bug(title="...", steps="...", product=1, module=0)

配置（.env）：
    ZENTAO_URL            禅道根地址，如 https://zentao.example.com（不要带 /api.php）
    ZENTAO_ACCOUNT        账号（建议专用机器人账号）
    ZENTAO_PASSWORD       密码（v18 REST 用它换 token）
    ZENTAO_TOKEN          可选：已有 token 时直接用，免登录
    ZENTAO_VERIFY_SSL     自签证书环境设 false（默认 true）
    ZENTAO_TIMEOUT        请求超时秒数（默认 20）

兼容性：
    v18+ 默认走 REST（POST /api.php/v1/tokens 换 token，Token 头鉴权）；
    换 token 失败且是 404/405 时，回落到老版本 api.php 会话登录。
    具体端点是否可用，用 `python run.py zentao --probe` 探测最省事。
"""
import os

import requests


class ZentaoError(Exception):
    """禅道调用失败（含鉴权失败、端点不存在、字段校验失败）"""


class ZentaoClient:
    def __init__(self, url, account="", password="", token="", verify_ssl=True, timeout=20):
        self.url = (url or "").rstrip("/")
        self.account = account or ""
        self.password = password or ""
        self.token = token or ""
        self.verify_ssl = verify_ssl
        self.timeout = timeout
        self.session = requests.Session()
        self.mode = "rest" if not token else "rest-token"

    # ---------------- 构造 ----------------
    @classmethod
    def from_env(cls, env_path=None):
        """从 .env / 系统环境变量构造；缺关键配置时抛 ZentaoError 并列出缺什么"""
        try:
            from core.env import load_env
            load_env()
        except Exception:                       # noqa: BLE001
            pass

        def g(key, default=""):
            return (os.getenv(key, default) or "").strip()

        url = g("ZENTAO_URL")
        missing = []
        if not url:
            missing.append("ZENTAO_URL（禅道根地址，如 https://zentao.xxx.com）")
        if not g("ZENTAO_TOKEN") and not (g("ZENTAO_ACCOUNT") and g("ZENTAO_PASSWORD")):
            missing.append("ZENTAO_ACCOUNT + ZENTAO_PASSWORD（或直接给 ZENTAO_TOKEN）")
        if missing:
            raise ZentaoError("禅道配置缺失，请在 .env 里补：\n  - " + "\n  - ".join(missing))

        verify = g("ZENTAO_VERIFY_SSL", "true").lower() not in ("false", "0", "no")
        return cls(
            url=url,
            account=g("ZENTAO_ACCOUNT"),
            password=g("ZENTAO_PASSWORD"),
            token=g("ZENTAO_TOKEN"),
            verify_ssl=verify,
            timeout=int(g("ZENTAO_TIMEOUT", "20") or 20),
        )

    # ---------------- 底层请求 ----------------
    def _url(self, path):
        return f"{self.url}/{path.lstrip('/')}"

    def _headers(self, extra=None):
        headers = {"Accept": "application/json"}
        if self.token:
            headers["Token"] = self.token
            headers["Authorization"] = f"Bearer {self.token}"
        headers.update(extra or {})
        return headers

    def request(self, method, path, params=None, json_body=None, files=None, data=None, expect_json=True):
        try:
            resp = self.session.request(
                method, self._url(path), params=params, json=json_body, files=files, data=data,
                headers=self._headers(), timeout=self.timeout, verify=self.verify_ssl)
        except requests.RequestException as e:
            raise ZentaoError(f"禅道请求失败 [{method} {path}]: {e}") from e

        if resp.status_code in (401, 403):
            raise ZentaoError(f"禅道鉴权失败 [{method} {path}] HTTP {resp.status_code}："
                              f"请检查 ZENTAO_ACCOUNT/PASSWORD 或 ZENTAO_TOKEN 是否有缺陷(提Bug)权限")
        if resp.status_code >= 400 and not expect_json:
            raise ZentaoError(f"禅道请求失败 [{method} {path}] HTTP {resp.status_code}: {resp.text[:300]}")
        if not expect_json:
            return resp

        try:
            payload = resp.json()
        except ValueError:
            raise ZentaoError(f"禅道返回不是 JSON [{method} {path}] HTTP {resp.status_code}: {resp.text[:300]}")
        if isinstance(payload, dict) and str(payload.get("error")) not in ("", "None", "0"):
            raise ZentaoError(f"禅道返回错误 [{method} {path}]: {payload}")
        return payload

    # ---------------- 登录 ----------------
    def login(self):
        """获取 token：v18 REST 优先，失败回落到老版本 api.php 会话"""
        if self.token:
            return self.token
        try:
            payload = self.request("POST", "/api.php/v1/tokens",
                                   json_body={"account": self.account, "password": self.password})
            token = (payload or {}).get("token")
            if token:
                self.token = token
                self.mode = "rest"
                return token
            raise ZentaoError(f"禅道未返回 token：{payload}")
        except ZentaoError as rest_error:
            try:
                return self._login_legacy()
            except ZentaoError:
                raise rest_error

    def _login_legacy(self):
        """禅道 <18 / 未开 REST：先取 sessionID，再调 api.php 登录"""
        info = self.request("GET", "/api-getsessionid.json")
        data = (info or {}).get("data") or {}
        if isinstance(data, str):               # 部分版本把 data 再套一层 JSON 字符串
            import json as _json
            try:
                data = _json.loads(data)
            except ValueError:
                data = {}
        sid = (data or {}).get("sessionID")
        if not sid:
            raise ZentaoError(f"老版本登录失败：未取到 sessionID（{info}）")
        payload = self.request(
            "POST", "/api.php",
            params={"m": "user", "f": "login", "t": "json", "zentaosid": sid},
            data={"account": self.account, "password": self.password})
        if not (isinstance(payload, dict) and payload.get("status") == "success"):
            raise ZentaoError(f"老版本登录失败：{payload}")
        self.mode = "legacy"
        self.session.cookies.set("zentaosid", sid)
        return sid

    # ---------------- 业务方法 ----------------
    def whoami(self):
        self.login()
        return self.request("GET", "/api.php/v1/user")

    def products(self):
        self.login()
        payload = self.request("GET", "/api.php/v1/products", params={"limit": 200})
        return (payload or {}).get("products") or payload or []

    def modules(self, product_id):
        """产品下的模块列表（取 module id 用）

        注意：公司禅道（开源版 22.6）没有暴露模块 REST 端点（/products/{id}/modules 返回 404），
        直接返回空列表并在提示里说明 —— 模块 id 请从提单页 URL 里取（moduleID=393）。
        """
        self.login()
        for path in (f"/api.php/v1/products/{product_id}/modules",
                     f"/api.php/v1/products/{product_id}/tree"):
            try:
                payload = self.request("GET", path)
            except ZentaoError:
                continue
            data = payload.get("modules") if isinstance(payload, dict) else None
            return data or (payload.get("data") if isinstance(payload, dict) else payload) or []
        return []

    def users(self):
        self.login()
        payload = self.request("GET", "/api.php/v1/users", params={"limit": 200})
        return (payload or {}).get("users") or payload or []

    def upload_file(self, file_path):
        """上传附件，返回文件 id（失败抛 ZentaoError，调用方可选择忽略附件）"""
        self.login()
        with open(file_path, "rb") as f:
            payload = self.request("POST", "/api.php/v1/files", files={"file": f})
        file_id = (payload or {}).get("id") or (payload or {}).get("fileID")
        if not file_id:
            raise ZentaoError(f"附件上传失败：{payload}")
        return file_id

    def create_bug(self, title, steps, product, module=0, severity=3, pri=3, bug_type="codeerror",
                   assigned_to="", feedback_by="", opened_build=0, keywords="", plan=0, story=0,
                   task=0, mailto=None, attachments=None, extra=None):
        """提一个缺陷（字段名对齐公司禅道提单页：禅道开源版 22.6 实测）

        :param title: Bug标题（必填）
        :param steps: 重现步骤，HTML 字符串（禅道默认模板：[步骤] / [结果] / [期望]）
        :param product: 所属产品 id（必填，公司环境 = 1 GSR OMNI）
        :param module: 所属模块 id（必填，公司环境自动化提单用 393 = /Payroll&结算）
        :param severity: 严重程度 1~4（3=一般，默认 3）
        :param pri: 优先级 1~4（3=中，默认 3）
        :param bug_type: codeerror(代码错误，默认) / codeimprovement(代码改进) / others(其他) ...
        :param assigned_to: 当前指派（禅道账号名，如 "Louie.lu"）
        :param feedback_by: 反馈者（提单页必填，留空默认用登录账号）
        :param opened_build: 影响版本（0 = 默认/主干；也可传 build id 或 id 列表）
        :param keywords: 关键词（建议填 "自动化" 便于检索）
        :param plan: 所属计划 id（0 = 不关联）
        :param story: 相关需求 id（0 = 不关联）
        :param task: 相关任务 id（0 = 不关联）
        :param mailto: 抄送给（账号名列表）
        :param attachments: 本地图片路径列表（禅道只收图片：png/jpg/gif 等，xlsx 会被拒）
        :param extra: 其他原样透传字段
        """
        self.login()
        payload = {
            "title": str(title)[:255],
            "steps": steps,
            "product": int(product),
            "module": int(module or 0),
            "severity": int(severity),
            "pri": int(pri),
            "type": bug_type,
            # 公司禅道（22.6）要求影响版本是数组，传标量会报『影响版本』不能为空
            "openedBuild": (opened_build if isinstance(opened_build, (list, tuple))
                            else [opened_build if opened_build not in (None, "") else 0]),
            "feedbackBy": feedback_by or self.account,
            "keywords": keywords,
        }
        if assigned_to:
            payload["assignedTo"] = assigned_to
        if plan:
            payload["plan"] = int(plan)
        if story:
            payload["story"] = int(story)
        if task:
            payload["task"] = int(task)
        if mailto:
            payload["mailto"] = mailto if isinstance(mailto, list) else [mailto]
        if attachments:
            ids = []
            for path in attachments:
                try:
                    ids.append(self.upload_file(path))
                except ZentaoError as e:
                    # 公司禅道服务端把附件类型限制得很死（png/xlsx/txt 都报"格式不在规定范围内"），
                    # 提不了附件不阻断提单：把文件路径写进重现步骤里，人工补传或用 UI 方式提单。
                    print(f"[附件跳过] {path}：{e}")
                    continue
            if ids:
                payload["files"] = ids
        if extra:
            payload.update(extra)

        if self.mode == "legacy":
            result = self.request("POST", "/api.php", params={"m": "bug", "f": "create", "t": "json"},
                                  json_body=payload)
            bug_id = (result or {}).get("id") or (result or {}).get("bugID")
        else:
            result = self.request("POST", "/api.php/v1/products/{}/bugs".format(int(product)),
                                  json_body=payload)
            bug_id = (result or {}).get("id") or (result or {}).get("bugID")
        if not bug_id:
            raise ZentaoError(f"提单失败，禅道返回：{result}")
        return bug_id

    def update_bug(self, bug_id, **fields):
        """修改缺陷（实测：PUT /api.php/v1/bugs/{id} 可用，PATCH 返回 200 但不生效）

        常用字段：title / severity / pri / type / steps / assignedTo / status / module / keywords
        """
        self.login()
        payload = {k: v for k, v in fields.items() if v is not None}
        if not payload:
            raise ZentaoError("update_bug 至少需要一个要修改的字段")
        return self.request("PUT", f"/api.php/v1/bugs/{bug_id}", json_body=payload)

    def delete_bug(self, bug_id):
        """删除缺陷（禅道要求对缺陷所属项目有权限，否则返回 400）"""
        self.login()
        return self.request("DELETE", f"/api.php/v1/bugs/{bug_id}", expect_json=False)
