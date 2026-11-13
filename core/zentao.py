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
        sid = ((info or {}).get("data") or {}).get("sessionID")
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
        """产品下的模块列表（取 module id 用；不同版本端点略有差异，失败会抛 ZentaoError）"""
        self.login()
        for path in (f"/api.php/v1/products/{product_id}/modules",
                     f"/api.php/v1/products/{product_id}/tree"):
            try:
                payload = self.request("GET", path)
            except ZentaoError:
                continue
            data = payload.get("modules") if isinstance(payload, dict) else None
            return data or (payload.get("data") if isinstance(payload, dict) else payload) or []
        raise ZentaoError(f"取模块失败：禅道 {self.url} 不支持上述模块端点，"
                          f"可先用 `python run.py zentao --probe` 看支持哪些接口")

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
                   assigned_to="", opened_build="", story=0, keywords="", attachments=None,
                   extra=None):
        """提一个缺陷

        :param title: 标题（必填）
        :param steps: 重现步骤（纯文本，支持禅道 markdown/富文本）
        :param product: 产品 id
        :param module: 模块 id（0 = 根模块）
        :param severity: 严重程度 1~4（1 最严重）
        :param pri: 优先级 1~4（1 最高）
        :param bug_type: codeerror(代码错误) / config(配置) / install(安装) / security(安全) /
                         performance(性能) / standard(标准规范) / automation(自动化) / designdefect(设计缺陷) /
                         others(其他)
        :param assigned_to: 指派给（禅道账号名，留空 = 默认）
        :param opened_build: 影响版本 id（可留空）
        :param story: 关联需求 id（可留空/0）
        :param attachments: 本地文件路径列表（会先上传再关联）
        :param extra: 其他原样透传字段（不同禅道版本字段有差异时用它兜底）
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
            "openedBuild": opened_build or "trunk",
            "keywords": keywords,
        }
        if assigned_to:
            payload["assignedTo"] = assigned_to
        if story:
            payload["story"] = int(story)
        if attachments:
            ids = []
            for path in attachments:
                try:
                    ids.append(self.upload_file(path))
                except ZentaoError:
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
