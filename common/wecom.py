"""企业微信群机器人通知（会话结束时由框架直接推送）

只需要一个群机器人 Webhook 地址（配置在 .env / 系统环境变量 WECOM_WEBHOOK）：
    群里右上角「…」→ 群机器人 → 添加机器人 → 复制 Webhook 地址

设计要点：
1、没有配置 webhook 时所有函数静默跳过，只打一行 INFO，本地执行完全无感；
2、发送失败只记 WARNING，绝不影响用例本身的执行结论；
3、机器人限制「20 条 / 分钟」，所以只在会话结束时聚合发送一条。
"""
import os
import requests
from config.setting import setting
from common.logger import logger


def _truncate_bytes(text: str, max_bytes: int = None) -> str:
    """按字节截断（企微限制的是字节数而不是字符数，1 个中文 = 3 字节）

    上限取自 setting.WECOM_MAX_CONTENT_BYTES（默认 4000，企微硬性上限 4096），可用环境变量覆盖。
    """
    max_bytes = max_bytes or setting.WECOM_MAX_CONTENT_BYTES
    data = (text or "").encode("utf-8")
    if len(data) <= max_bytes:
        return text
    return data[:max_bytes].decode("utf-8", errors="ignore") + "…"


def _disabled_reason(webhook=None):
    """返回"不发送通知"的原因；返回 None 表示可以发送

    统一判断两个开关：WECOM_ENABLE（总开关，默认 true）、WECOM_WEBHOOK（没配就不发）
    """
    if not setting.WECOM_ENABLE:
        return "WECOM_ENABLE=false（通知已关闭）"
    if not (webhook or setting.WECOM_WEBHOOK):
        return "未配置 WECOM_WEBHOOK"
    return None


def send_markdown(webhook: str, content: str) -> bool:
    """发送 markdown 消息；未开启通知或没配 webhook 时跳过"""
    reason = _disabled_reason(webhook)
    if reason:
        logger.info(f"跳过企业微信通知：{reason}")
        return False
    try:
        resp = requests.post(
            webhook,
            json={"msgtype": "markdown", "markdown": {"content": _truncate_bytes(content)}},
            timeout=setting.WECOM_TIMEOUT,
        )
        result = resp.json()
        if result.get("errcode") == 0:
            logger.info("企业微信通知发送成功")
            return True
        logger.warning(f"企业微信通知发送失败：{result}")
        return False
    except Exception as e:
        logger.warning(f"企业微信通知发送异常（不影响用例结果）：{e}")
        return False


def send_file(webhook: str, file_path: str) -> bool:
    """把文件（例如结果 Excel）发到群里：先上传拿 media_id，再发 file 消息"""
    if _disabled_reason(webhook) or not file_path or not os.path.isfile(file_path):
        return False
    try:
        key = webhook.split("key=")[-1]
        with open(file_path, "rb") as f:
            upload = requests.post(
                f"https://qyapi.weixin.qq.com/cgi-bin/webhook/upload_media?key={key}&type=file",
                files={"media": f},
                timeout=60,
            )
        media_id = upload.json().get("media_id")
        if not media_id:
            logger.warning(f"上传文件到企业微信失败：{upload.text[:200]}")
            return False
        resp = requests.post(
            webhook, json={"msgtype": "file", "file": {"media_id": media_id}}, timeout=setting.WECOM_TIMEOUT
        )
        ok = resp.json().get("errcode") == 0
        logger.info(f"结果文件推送{'成功' if ok else '失败'}：{os.path.basename(file_path)}")
        return ok
    except Exception as e:
        logger.warning(f"发送文件到企业微信异常（不影响用例结果）：{e}")
        return False


def notify(webhook: str, project: str, summary: str, failed_cases=None,
           result_files=None, report_url: str = None) -> bool:
    """组装并发送执行结果卡片（webhook 为空则跳过）

    :param webhook: 群机器人 Webhook 地址
    :param project: 当前用例项目（假勤 / 调试）
    :param summary: 统计文本，例如「通过 8 失败 4 跳过 21」
    :param failed_cases: 失败用例列表 ["5-年假（按duration算endtime）", ...]
    :param result_files: 本次生成的结果文件路径列表
    :param report_url: allure 报告链接（Jenkins 下自动取 BUILD_URL）
    """
    reason = _disabled_reason(webhook)
    if reason:
        logger.info(f"跳过企业微信通知：{reason}")
        return False

    failed_cases = failed_cases or []
    lines = [
        "## 接口自动化执行结果",
        f"> 项目：{project}",
        f"> 结果：{summary}",
    ]
    if failed_cases:
        show = "、".join(failed_cases[:10])
        more = f"（共 {len(failed_cases)} 条，仅列前 10 条）" if len(failed_cases) > 10 else ""
        lines.append(f'> <font color="warning">失败用例：{show}{more}</font>')
    else:
        lines.append('> <font color="info">失败用例：无</font>')
    if result_files:
        lines.append(f"> 结果文件：{os.path.basename(result_files[0])}")
    if report_url:
        lines.append(f"> [查看 Allure 报告]({report_url})")
    return send_markdown(webhook, "\n".join(lines))

