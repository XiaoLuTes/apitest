"""一次 pytest 会话内的运行时状态（由 conftest 在会话开始时重置）
作用有两个：
1、变量依赖状态（减少"连环失败"的报告噪声）
   某条用例失败 / 跳过后，它 extract 出来的变量会被标记为"不可信"；
2、用例结果计数
   统计本次执行的 通过 / 失败 / 跳过 条数，用于结果文件命名与收尾汇总。
"""
from api.common.logger import logger

# 用例失败时是否连带把下游变量判定为不可信：config/setting.py 的 INVALIDATE_ON_ANY_FAILURE

untrusted = {}
outcomes = {"passed": 0, "failed": 0, "skipped": 0}
failed_case_list = []  # 用于通知 / 汇总里列出失败用例


sheet_outcomes = {}


def reset():
    """会话开始重置状态（conftest 调用）"""
    untrusted.clear()
    failed_case_list.clear()
    sheet_outcomes.clear()          # 清空分表计数，避免上一轮的残留
    for key in outcomes:
        outcomes[key] = 0


def record_outcome(outcome, case_id=None, name=None, sheet=None):
    """记录一条用例的执行结果

    :param outcome: 结果类型，取值 passed / failed / skipped
    :param case_id: 用例编号（失败时记录，便于通知里列出失败用例）
    :param name: 用例名称
    :param sheet: 用例所在的 sheet 名（用于分表统计；不传则只计入总数，不影响老逻辑）
    """
    # 总数计数器
    if outcome in outcomes:
        outcomes[outcome] += 1
    # 分表计数器
    if sheet:
        # setdefault：第一次遇到这个 sheet 时自动建一个全 0 的计数器；
        stat = sheet_outcomes.setdefault(sheet, {"passed": 0, "failed": 0, "skipped": 0})
        if outcome in stat:
            stat[outcome] += 1

    # 失败清单
    if outcome == "failed" and case_id is not None:
        failed_case_list.append((case_id, name))


def failed_cases():
    """本次执行失败的用例列表 [(用例编号, 用例名称)]"""
    return list(failed_case_list)


def summary():
    """返回本次执行的条数统计字典"""
    return dict(outcomes)


def summary_text():
    """返回便于阅读的统计文本，例如：通过 8 失败 4 跳过 21"""
    return f"通过 {outcomes['passed']} 失败 {outcomes['failed']} 跳过 {outcomes['skipped']}"


def sheet_summary():
    """返回按 sheet 分组的统计"""
    return {k: dict(v) for k, v in sheet_outcomes.items()}


def sheet_summary_text():
    """返回按 sheet 分组的统计文本（打日志）
    返回示例：数据准备 通过12 失败0 跳过0 | 测试执行 通过2 失败1 跳过0
    """
    parts = []
    for sheet, stat in sheet_outcomes.items():
        # 该 sheet 一条用例都没跑（比如空的 Sheet2）就跳过
        if sum(stat.values()) == 0:
            continue
        parts.append(f"{sheet} 通过{stat['passed']} 失败{stat['failed']} 跳过{stat['skipped']}")
    return " | ".join(parts)


def mark_untrusted(names, reason):
    """把变量标记为"不可信"（由失败 / 跳过的用例负责产出的变量）"""
    for name in (names or []):
        if name and name not in untrusted:
            untrusted[name] = reason
            logger.warning(f"变量 ${{{name}}} 标记为不可信：{reason}")


def is_untrusted(name):
    """变量是否已被标记为不可信"""
    return name in untrusted


def mark_trusted(names):
    """用例执行成功后，把它产出的变量重新置为可信（用于“同一变量被多条用例产出”的场景）"""
    for name in (names or []):
        if name in untrusted:
            untrusted.pop(name, None)
            logger.info(f"变量 ${{{name}}} 已重新产出，恢复为可信")


def untrusted_reason(name):
    """变量不可信的原因，未标记时返回 None"""
    return untrusted.get(name)


def untrusted_map():
    """返回当前所有不可信变量的副本"""
    return dict(untrusted)
