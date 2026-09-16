"""一次 pytest 会话内的运行时状态（由 conftest 在会话开始时重置）

作用有两个：

1、变量依赖状态（减少"连环失败"的报告噪声）
   某条用例失败 / 跳过后，它 extract 出来的变量会被标记为"不可信"；
   引用这些变量的后续用例会被直接跳过（skip），而不是拿着错误/缺失的变量
   继续发请求、再报一堆 `变量 ${x} 未定义`。
   这样报告里就是"1 条根因 + N 条 skipped"，根因一眼可见。

2、用例结果计数
   统计本次执行的 通过 / 失败 / 跳过 条数，用于结果文件命名与收尾汇总。
"""
from common.logger import logger

# 用例失败时是否连带把下游变量判定为不可信：该配置项已移到 config/setting.py 的 INVALIDATE_ON_ANY_FAILURE

_untrusted = {}
_outcomes = {"passed": 0, "failed": 0, "skipped": 0}
_failed_cases = []  # [(用例编号, 用例名称)]，用于通知 / 汇总里列出失败用例


def reset():
    """会话开始重置状态（conftest 调用）"""
    _untrusted.clear()
    _failed_cases.clear()
    for key in _outcomes:
        _outcomes[key] = 0


def record_outcome(outcome, case_id=None, name=None):
    """记录一条用例的执行结果

    :param outcome: 结果类型，取值 passed / failed / skipped
    :param case_id: 用例编号（失败时记录，便于通知里列出失败用例）
    :param name: 用例名称
    """
    if outcome in _outcomes:
        _outcomes[outcome] += 1
    if outcome == "failed" and case_id is not None:
        _failed_cases.append((case_id, name))


def failed_cases():
    """本次执行失败的用例列表 [(用例编号, 用例名称)]"""
    return list(_failed_cases)


def summary():
    """返回本次执行的条数统计字典"""
    return dict(_outcomes)


def summary_text():
    """返回便于阅读的统计文本，例如：通过 8 失败 4 跳过 21"""
    return f"通过 {_outcomes['passed']} 失败 {_outcomes['failed']} 跳过 {_outcomes['skipped']}"


def mark_untrusted(names, reason):
    """把变量标记为"不可信"（由失败 / 跳过的用例负责产出的变量）"""
    for name in (names or []):
        if name and name not in _untrusted:
            _untrusted[name] = reason
            logger.warning(f"变量 ${{{name}}} 标记为不可信：{reason}")


def is_untrusted(name):
    """变量是否已被标记为不可信"""
    return name in _untrusted


def mark_trusted(names):
    """用例执行成功后，把它产出的变量重新置为可信（用于“同一变量被多条用例产出”的场景）"""
    for name in (names or []):
        if name in _untrusted:
            _untrusted.pop(name, None)
            logger.info(f"变量 ${{{name}}} 已重新产出，恢复为可信")


def untrusted_reason(name):
    """变量不可信的原因，未标记时返回 None"""
    return _untrusted.get(name)


def untrusted_map():
    """返回当前所有不可信变量的副本"""
    return dict(_untrusted)
