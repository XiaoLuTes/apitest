# -*- coding: utf-8 -*-
"""数据库操作环境护栏（接口用例集 / UI 用例集共用同一份实现）

硬约束（AGENTS.md 第 5 节）：只有测试环境允许连库，**包括只读查询**。
预生产 / 生产 / UAT / 客户演示环境一律禁止。

为什么放在 core/：护栏原来只写在 api/common/database.py 里，
UI 用例集的 sql / sql_update 动作走 ui/utils/database.py 就绕过了，
等于红线只守了一半。统一到 core 后两边调同一个函数，新增入口也必须复用。

用法：
    from core.db_guard import assert_env_allowed
    assert_env_allowed(settings.ENV, settings.DB_ALLOWED_ENVS)
"""
import os

# 默认白名单：只有测试环境
DEFAULT_ALLOWED = "测试环境"


def allowed_envs(raw=None):
    """把 DB_ALLOWED_ENVS 的原始值（逗号分隔）解析成列表

    取值优先级由调用方决定（一般已由 setting / settings 从环境变量读好）；
    传 None 时回落到环境变量 DB_ALLOWED_ENVS，再回落到「测试环境」。
    """
    text = os.getenv("DB_ALLOWED_ENVS", "") if raw is None else raw
    text = str(text or DEFAULT_ALLOWED)
    envs = [item.strip() for item in text.replace("，", ",").split(",") if item.strip()]
    return envs or [DEFAULT_ALLOWED]


def assert_env_allowed(current_env, allowed_raw=None):
    """当前环境不在白名单时抛错（拦在 connect() 之前，连不上库也连不上数据源）

    :param current_env: 当前运行环境（setting.ENV / settings.ENV）
    :param allowed_raw: 白名单原文（setting.DB_ALLOWED_ENVS），None 表示读环境变量
    :return: True
    """
    allowed = allowed_envs(allowed_raw)
    current = str(current_env or "").strip()
    if current not in allowed:
        raise RuntimeError(
            f"[数据库操作已拦截] 当前环境 ENV={current!r} 不在允许范围 {allowed}；"
            "按项目约束只有测试环境可以连接数据库（AGENTS.md 第 5 节）；"
            "确需调整请先找用户确认，不要改 DB_ALLOWED_ENVS 绕开护栏")
    return True
