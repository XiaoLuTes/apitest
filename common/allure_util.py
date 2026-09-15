"""把执行产物（用例结果文件等）附加到 allure 报告

allure 的附件必须在"用例执行过程中"产生，而用例结果文件是在会话结束时才生成的，
所以这里在会话收尾阶段直接向 allure 结果目录写入一条"汇总条目"：
    <uuid>-result.json     汇总记录（带附件声明）
    <uuid>-attachment.xlsx 结果文件本体
allure generate / serve 时会把它渲染成一条名为"用例执行结果文件"的记录，附件可直接下载。

注意：这条记录会被 allure 计入用例统计（每个结果文件 +1 条），它在报告里是独立 suite，
不会和真实用例混在一起。
"""
import json
import os
import shutil
import time
import uuid
from xml.sax.saxutils import escape

from config.setting import setting
from common.logger import logger

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def export_result_files(paths, title="用例执行结果文件"):
    """把结果文件作为附件写入 allure 结果目录，返回成功附加的文件名列表"""
    files = [p for p in (paths or []) if p and os.path.isfile(p)]
    if not files:
        logger.info("没有需要附加到 allure 报告的结果文件")
        return []

    allure_dir = setting.ALLURE_RESULT_PATH
    os.makedirs(allure_dir, exist_ok=True)
    exported = []
    now = int(time.time() * 1000)

    for path in files:
        name = os.path.basename(path)
        uid = uuid.uuid4().hex
        attachment = f"{uid}-attachment.xlsx"
        try:
            # 附件文件必须放在 allure 结果目录内，source 用相对文件名引用
            shutil.copy2(path, os.path.join(allure_dir, attachment))
            result = {
                "uuid": uid,
                "historyId": "excel-result-file",
                "fullName": f"reports.results.{name}",
                "name": f"{title}：{name}",
                "status": "passed",
                "statusDetails": {},
                "stage": "finished",
                "start": now,
                "stop": now,
                "labels": [
                    {"name": "suite", "value": "用例执行结果"},
                    {"name": "host", "value": os.environ.get("COMPUTERNAME", "local")},
                ],
                "attachments": [
                    {"name": name, "source": attachment, "type": XLSX_MIME}
                ],
            }
            with open(os.path.join(allure_dir, f"{uid}-result.json"), "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False)
            exported.append(name)
            logger.info(f"已把结果文件附加到 allure 报告：{name}")
        except Exception as e:
            logger.error(f"结果文件附加到 allure 报告失败：{path}，错误信息：{str(e)}", exc_info=True)

    _write_environment(allure_dir, exported)
    return exported


def _write_environment(allure_dir, exported):
    """在 allure 报告首页的 Environment 面板登记环境信息与结果文件名

    用 environment.xml（UTF-8）而不是 environment.properties：
    allure 按 ISO-8859-1 读取 .properties，中文会变成 ???。
    """
    if not exported:
        return
    try:
        items = [
            ("env", setting.ENV),
            ("project", setting.CURRENT_PROJECT),
        ]
        items += [(f"result_file_{i}", name) for i, name in enumerate(exported, start=1)]
        items.append(("result_path", str(setting.RESULT_PATH)))

        lines = ['<?xml version="1.0" encoding="UTF-8"?>', "<environment>"]
        for key, value in items:
            lines.append("    <parameter>")
            lines.append(f"        <key>{escape(str(key))}</key>")
            lines.append(f"        <value>{escape(str(value))}</value>")
            lines.append("    </parameter>")
        lines.append("</environment>")

        with open(os.path.join(allure_dir, "environment.xml"), "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
    except Exception as e:
        logger.warning(f"写入 allure environment.xml 失败：{str(e)}")
