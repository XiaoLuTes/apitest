"""企业微信群机器人通知（测试会话结束时推送）

只需一个群机器人 Webhook（配置在 .env / Jenkins 环境变量 WECOM_WEBHOOK）：
    群里右上角「…」→ 群机器人 → 添加机器人 → 复制 Webhook 地址

设计要点（与 api 项目保持一致）：
1、未配置 webhook 时所有函数静默跳过，只打一行 INFO，本地执行完全无感；
2、发送失败只记 WARNING，绝不影响用例本身的执行结论；
3、机器人限制「20 条 / 分钟」，所以只在会话结束时聚合发送一条。
"""
import base64
import hashlib
import os
import requests
from ui.utils.logger import logger

# 群机器人 markdown 内容上限 4096 字节（UTF-8），留点余量
MAX_CONTENT_BYTES = 4000
DEFAULT_TIMEOUT = 10


def _truncate_bytes(text, max_bytes=MAX_CONTENT_BYTES):
    """按字节截断（企微限制的是字节数而不是字符数，1 个中文 = 3 字节）"""
    data = (text or "").encode("utf-8")
    if len(data) <= max_bytes:
        return text
    return data[:max_bytes].decode("utf-8", errors="ignore") + "…"


def send_markdown(webhook, content):
    """发送 markdown 消息；webhook 为空时直接跳过"""
    if not webhook:
        logger.info("未配置 WECOM_WEBHOOK，跳过企业微信通知")
        return False
    try:
        resp = requests.post(
            webhook,
            json={"msgtype": "markdown", "markdown": {"content": _truncate_bytes(content)}},
            timeout=DEFAULT_TIMEOUT,
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


def send_image(webhook, image_path):
    """发送图片消息（登录二维码推送用）；webhook 为空 / 文件不存在时静默跳过
    企业微信机器人图片限制：base64 后不超过 2MB，超过只能改用 send_file
    """
    if not webhook or not image_path or not os.path.isfile(image_path):
        return False
    try:
        with open(image_path, "rb") as f:
            raw = f.read()
        if len(raw) > 2 * 1024 * 1024:
            logger.warning(f"图片超过 2MB，企业微信机器人无法发送: {image_path}")
            return False
        b64 = base64.b64encode(raw).decode("ascii")
        md5 = hashlib.md5(raw).hexdigest()
        resp = requests.post(
            webhook,
            json={"msgtype": "image", "image": {"base64": b64, "md5": md5}},
            timeout=DEFAULT_TIMEOUT,
        )
        result = resp.json()
        if result.get("errcode") == 0:
            logger.info(f"图片已推送到企业微信: {os.path.basename(image_path)}")
            return True
        logger.warning(f"图片推送失败: {result}")
        return False
    except Exception as e:
        logger.warning(f"图片推送异常（不影响用例）: {e}")
        return False


def send_file(webhook, file_path):
    """把文件（例如测试结果 Excel / YAML）发到群里：先上传拿 media_id，再发 file 消息"""
    if not webhook or not file_path or not os.path.isfile(file_path):
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
            webhook, json={"msgtype": "file", "file": {"media_id": media_id}}, timeout=DEFAULT_TIMEOUT
        )
        ok = resp.json().get("errcode") == 0
        logger.info(f"结果文件推送{'成功' if ok else '失败'}：{os.path.basename(file_path)}")
        return ok
    except Exception as e:
        logger.warning(f"发送文件到企业微信异常（不影响用例结果）：{e}")
        return False


def notify(webhook, project, summary, failed_cases=None,
           result_files=None, report_url=None):
    """组装并发送执行结果卡片（webhook 为空则跳过）

    :param webhook: 群机器人 Webhook 地址
    :param project: 当前用例项目（settings.CURRENT_PROJECT）
    :param summary: 统计文本，例如「通过 8 失败 4 共 12」
    :param failed_cases: 失败用例列表 ["招聘平台-2 创建启用ai岗位", ...]
    :param result_files: 本次生成的结果文件路径列表
    :param report_url: 报告链接（Jenkins 下自动取 BUILD_URL）
    """
    if not webhook:
        logger.info("未配置 WECOM_WEBHOOK，跳过企业微信通知")
        return False

    failed_cases = failed_cases or []
    lines = [
        "## UI自动化执行结果",
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
        lines.append(f"> [查看构建详情]({report_url})")
    return send_markdown(webhook, "\n".join(lines))
