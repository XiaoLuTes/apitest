"""统一 .env 加载（不引入额外依赖，python-dotenv 可选）

规则与原先两个框架保持一致：
    KEY=VALUE，# 开头为注释，空行忽略，值两端引号会被去掉；
    已经存在的系统环境变量优先，不会被 .env 覆盖（便于 Jenkins / CI 用环境变量注入）。
"""
import os

from core.paths import ROOT

_ENV_FILE = os.path.join(ROOT, ".env")
_loaded = False


def load_env(path: str = None) -> None:
    """加载 .env（进程内只加载一次；重复调用直接返回）"""
    global _loaded
    if _loaded:
        return
    _loaded = True
    env_path = path or _ENV_FILE
    if not os.path.isfile(env_path):
        return
    try:
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key:
                    os.environ.setdefault(key, value)
    except OSError:
        pass
