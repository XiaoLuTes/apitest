#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""用例静态检查（lint）——执行前的第一道「机器初审」

只做静态分析：不连数据库、不连业务系统、不启动浏览器，秒级返回。
检查的是「格式 / 引用 / 结构」层的问题（会让用例一跑就崩或静默空转的错误），
不判断业务预期是否正确（那是执行 + 断言 + 人工评审的事）。

用法：
    python tools/lint_cases.py                        # 全查：接口用例 + 所有 UI 项目
    python tools/lint_cases.py --suite api            # 只查接口用例
    python tools/lint_cases.py --suite ui             # 只查 UI 用例
    python tools/lint_cases.py --project 薪资包结算     # 只查指定项目（可重复）
    python tools/lint_cases.py --file api/testcase/x.xlsx --file ui/testcases/x.yaml
    python tools/lint_cases.py --strict               # 警告也视为失败（可用于 CI 门禁）
    python tools/lint_cases.py --format json          # 输出 JSON，便于解析

合法动作集合不是手写清单，而是从以下代码里反射出来的，动作增删后自动跟随：
    接口方法/特殊动作  api/common/executor.py + api/common/request_util.py
    UI 动作            ui/utils/executor.py
"""
import argparse
import difflib
import glob
import json
import os
import re
import sys
from dataclasses import dataclass, field

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from core import paths  # noqa: E402

ERROR = "ERROR"
WARN = "WARN"

# ============================================================================
# 问题模型
# ============================================================================


@dataclass
class Issue:
    level: str
    code: str
    msg: str
    file: str = ""
    sheet: str = ""
    row: int = 0
    case: str = ""

    def as_dict(self):
        return {
            "level": self.level, "code": self.code, "msg": self.msg,
            "file": self.file, "sheet": self.sheet, "row": self.row, "case": self.case,
        }

    def location(self):
        parts = []
        if self.sheet:
            parts.append(self.sheet)
        if self.row:
            parts.append(f"第{self.row}行")
        return "/".join(parts)

    def __str__(self):
        loc = self.location()
        head = f"[{self.level}] {loc + ' ' if loc else ''}"
        if self.case:
            head += f"{self.case}｜"
        return f"{head}{self.msg}"


class Collector:
    def __init__(self):
        self.issues = []
        self.files = []          # [(路径, 用例条数)]

    def add(self, level, code, msg, **kwargs):
        self.issues.append(Issue(level, code, msg, **kwargs))

    def error(self, code, msg, **kwargs):
        self.add(ERROR, code, msg, **kwargs)

    def warn(self, code, msg, **kwargs):
        self.add(WARN, code, msg, **kwargs)

    def count(self, level, file=None):
        return sum(1 for i in self.issues
                   if i.level == level and (file is None or i.file == file))

    @property
    def errors(self):
        return self.count(ERROR)

    @property
    def warnings(self):
        return self.count(WARN)


# ============================================================================
# 从代码反射合法动作 / 请求方法（不手写清单，代码变了自动跟随）
# ============================================================================


def _read(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except OSError:
        return ""


def api_method_sets():
    """返回 (所有合法 method, 需要特殊前置参数的 method)"""
    base = {"get", "post", "put", "patch", "delete", "head", "options", "upload", "download"}
    src = _read(os.path.join(paths.API_ROOT, "common", "executor.py"))
    special = set(re.findall(r"method\s*==\s*['\"]([a-z_]+)['\"]", src))
    return base | special, special


def ui_action_sets():
    """返回 (所有合法 action, 不需要元素的 action)"""
    src = _read(os.path.join(paths.UI_ROOT, "utils", "executor.py"))
    actions = set(re.findall(r'action\s*==\s*"([a-z_]+)"', src))
    # 兜底：万一正则没匹配到（代码风格变化），用已知集合，避免把全部动作误判为非法
    if len(actions) < 5:
        actions = {"input", "click", "check_text", "check_value", "save_text", "save_value",
                   "down", "up", "enter", "check_exists", "wait_exists", "wait_exists_refresh",
                   "submit", "download", "edit_excel", "upload", "wait", "screenshot",
                   "wait_text", "wait_value", "sql", "sql_update"}
    no_element = {"wait", "screenshot", "enter", "down", "up", "sql", "sql_update", "edit_excel"}
    return actions, no_element


API_METHODS, API_SPECIAL_METHODS = api_method_sets()
UI_ACTIONS, UI_NO_ELEMENT_ACTIONS = ui_action_sets()

DB_METHODS = {"db_select", "db_update"}
NO_URL_METHODS = DB_METHODS | {"editexcel", "pkgquery"}
API_REQUIRED_COLUMNS = ["case_id", "name", "headers", "method", "url", "data", "validata"]
API_RECOMMENDED_COLUMNS = ["response", "result", "extract"]
API_SHEET_NAMES = {"数据准备", "测试执行", "数据清理", "测试准备", "数据校验"}

VAR_RE = re.compile(r"\$\{([^}]*)\}")
UNCLOSED_VAR_RE = re.compile(r"\$\{[^}]*$")
UI_VAR_RE = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")
UI_PRELOAD_VARS = {"username", "password", "customer", "owner", "replace_num"}


def _suggest(name, candidates):
    close = difflib.get_close_matches(str(name), [str(c) for c in candidates], n=1, cutoff=0.6)
    return f"（相近：{close[0]}）" if close else ""


def _as_text(value):
    """把任意单元格值转成用于扫描变量的文本"""
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        try:
            return json.dumps(value, ensure_ascii=False)
        except (TypeError, ValueError):
            return str(value)
    return str(value)


def _is_blank(value):
    return value is None or (isinstance(value, str) and not value.strip())


def _json_obj(value):
    """把 Excel 单元格里的 JSON 文本（或已解析的 dict/list）统一成 Python 对象；解析失败返回 None"""
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str) and value.strip().startswith(("{", "[")):
        try:
            return json.loads(value)
        except ValueError:
            return None
    return None


def scan_variables(text):
    """返回 (引用到的变量名列表, 是否有未闭合的 ${)"""
    if not text:
        return [], False
    unclosed = bool(UNCLOSED_VAR_RE.search(text))
    return [m.strip() for m in VAR_RE.findall(text)], unclosed


# ============================================================================
# 接口侧：Excel 用例
# ============================================================================


def api_globals():
    """全局可用变量：variable/all.yaml 的键 + .env 注入的键（user_token 等）

    注意：刻意不读 extract.yaml——那是上一轮执行留下的运行期产物，用它兜底会把
    「变量其实没定义」的用例误判为通过。
    """
    keys = set()
    try:
        import yaml
        from api.config.setting import setting
        with open(setting.ALL_YAML, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        if isinstance(data, dict):
            keys |= set(data.keys())
        keys |= set(setting.ENV_VARIABLES.keys())
    except SystemExit as e:               # 项目名非法时 setting 会抛 SystemExit
        print(f"[lint] 读取接口全局变量失败：{e}", file=sys.stderr)
    except Exception as e:                # noqa: BLE001
        print(f"[lint] 读取接口全局变量失败：{e}", file=sys.stderr)
    return keys


def api_projects():
    try:
        from api.config.setting import setting
        return dict(setting.TEST_FLIELOADS)
    except Exception:                     # noqa: BLE001
        return {}


def _api_retry_check(collector, value, ctx):
    """retry 列只认：空 / 数字 / dict{times,interval}"""
    if _is_blank(value):
        return
    try:
        from api.common import retry as retry_mod
        retry_mod.resolve(value)
    except ValueError as e:
        collector.error("API-RETRY", str(e).split("，可写次数")[0], **ctx)
    except Exception:                     # noqa: BLE001
        pass


def _api_validata_check(collector, method, validata, ctx):
    """断言格式：db_select 用「字段=值」，其余用 JSON {jsonpath: 期望值}"""
    if _is_blank(validata):
        if method in API_SPECIAL_METHODS and method != "download":
            pass
        return
    text = str(validata).strip()

    if method == "db_select":
        if text.startswith("{") and "$" in text:
            collector.error(
                "API-DB-ASSERT",
                "db_select 的断言是「字段=值[,字段=值]」形式（如 status=2），不是 JSON 断言", **ctx)
        elif "=" not in text and text.lower() not in ("empty", "[]", "null", "none") \
                and not text.startswith(("count:", "count>:", "contains:")):
            collector.warn(
                "API-DB-ASSERT",
                f"db_select 断言 [{text}] 可能无法识别，支持：字段=值 / count:n / count>:n / contains:x / empty", **ctx)
        return

    if method == "pkgquery":
        # pkgquery 的断言是「字段=值[,字段=值]」，字段可以写变量名或接口字段名
        if "=" not in text:
            collector.error("API-PKGQUERY",
                            f"pkgquery 的 validata 应为 字段=值[,字段=值]（如 pkg_status=0），当前：[{text}]", **ctx)
        return

    if method == "db_update":
        if re.match(r"^\s*(update|insert|delete|set)\b", text, re.I) or re.search(r"\bset\s+\w+\s*=", text, re.I):
            collector.error(
                "API-DB-ASSERT",
                "db_update 的 validata 是「影响行数」断言，SQL 语句必须写在 data 列（常见错误：把 SET autocommit=1 写进断言列）",
                **ctx)
        elif not re.match(r"^\d+$", text) and text.lower() not in ("empty", "null", "none") \
                and not text.startswith(("count:", "count>:")):
            collector.warn("API-DB-ASSERT", f"db_update 断言 [{text}] 不常见，支持：数字 / count:n / count>:n / empty",
                           **ctx)
        return

    if method == "download":
        collector.warn("API-DOWNLOAD", "download 不支持 validata 断言，该断言会被忽略", **ctx)
        return

    try:
        parsed = json.loads(text)
    except (TypeError, ValueError):
        collector.error("API-ASSERT",
                        f"validata 不是合法 JSON：{text[:60]}（应为 {{\"$.code\": 200, ...}}）", **ctx)
        return
    if not isinstance(parsed, dict):
        collector.error("API-ASSERT", f"validata 必须是 JSON 对象（{{jsonpath: 期望值}}），当前是 {type(parsed).__name__}",
                        **ctx)
        return
    if not parsed:
        collector.warn("API-ASSERT", "validata 是空对象 {}，等于不做断言（用例可能白跑）", **ctx)
    for key in parsed.keys():
        if not str(key).startswith("$"):
            collector.error("API-ASSERT", f"断言键 [{key}] 不是合法 jsonpath（应以 $ 开头，如 $.data.id）", **ctx)


def _api_extract_check(collector, extract, ctx, available):
    """extract 列：{变量名: jsonpath}，并把变量名登记为后续用例可用"""
    if _is_blank(extract):
        return
    try:
        parsed = json.loads(str(extract))
    except (TypeError, ValueError):
        collector.error("API-EXTRACT", f"extract 不是合法 JSON：{str(extract)[:60]}", **ctx)
        return
    if not isinstance(parsed, dict):
        collector.error("API-EXTRACT", f"extract 必须是 JSON 对象（{{变量名: jsonpath}}），当前是 {type(parsed).__name__}",
                        **ctx)
        return
    for key, jsonpath in parsed.items():
        if not str(key).strip():
            collector.error("API-EXTRACT", "extract 存在空变量名", **ctx)
        if not str(jsonpath).strip().startswith("$"):
            collector.error("API-EXTRACT", f"extract 变量 [{key}] 的取值 [{jsonpath}] 不是合法 jsonpath（应以 $ 开头）",
                            **ctx)
        available.add(str(key).strip())


def _api_method_check(collector, method_raw, ctx):
    method = "" if method_raw is None else str(method_raw).strip().lower()
    if not method:
        collector.error("API-METHOD", "method 为空，无法执行", **ctx)
        return ""
    if method.startswith("upload:"):
        verb = method.split(":", 1)[1].strip()
        if verb not in ("post", "put", "patch"):
            collector.error("API-METHOD", f"upload 的动词只支持 post/put/patch，当前 [upload:{verb}]", **ctx)
        return "upload"
    if method not in API_METHODS:
        collector.error("API-METHOD",
                        f"method [{method}] 非法，支持：{'/'.join(sorted(API_METHODS))}"
                        f"{_suggest(method, API_METHODS)}", **ctx)
        return ""
    return method


def lint_api_file(path, collector, available):
    import openpyxl
    display = os.path.relpath(path, ROOT)
    try:
        wb = openpyxl.load_workbook(path, data_only=False)
    except Exception as e:                # noqa: BLE001
        collector.error("API-FILE", f"无法打开 Excel：{e}", file=display)
        return display, 0

    total = 0
    seen_ids = {}
    try:
        for sheet in wb.sheetnames:
            ws = wb[sheet]
            header = [c.value for c in ws[1]] if ws.max_row >= 1 else []
            header_names = [str(h).strip() if h is not None else "" for h in header]
            cols = {name: idx for idx, name in enumerate(header_names) if name}
            data_rows = []
            for row in range(2, ws.max_row + 1):
                values = [ws.cell(row=row, column=c).value for c in range(1, len(header_names) + 1)]
                if all(_is_blank(v) for v in values):
                    continue
                data_rows.append((row, values))
            if not data_rows:
                continue
            total += len(data_rows)

            # ---- 表头检查 ----
            if len(header_names) < 9:
                # 框架里 max_col < 9 的 sheet 会被整表跳过，所以这里只是提示，不是错误
                collector.warn("API-HEADER",
                               f"表头只有 {len(header_names)} 列（<9 列），执行时该 sheet 会被整表跳过",
                               file=display, sheet=sheet)
                continue
            missing = [c for c in API_REQUIRED_COLUMNS if c not in cols]
            if missing:
                collector.error("API-HEADER", f"缺少必需列：{'、'.join(missing)}（执行时会 KeyError）",
                                file=display, sheet=sheet)
            dup = [c for c in set(header_names) if c and header_names.count(c) > 1]
            if dup:
                collector.error("API-HEADER", f"列头重复：{'、'.join(dup)}（后一列会覆盖前一列取值）",
                                file=display, sheet=sheet)
            for rec in API_RECOMMENDED_COLUMNS:
                if rec not in cols:
                    collector.warn("API-HEADER", f"建议补一列 {rec}（缺 result/response 时结果不会回写，缺 extract 时无法产出变量）",
                                   file=display, sheet=sheet)
            if len(wb.sheetnames) > 1 and sheet not in API_SHEET_NAMES:
                collector.warn("API-HEADER", f"sheet 名 [{sheet}] 不在约定集合 {sorted(API_SHEET_NAMES)} 内（不影响执行）",
                               file=display, sheet=sheet)

            # ---- 行级检查 ----
            for row, values in data_rows:
                record = {name: values[idx] for name, idx in cols.items()}
                case_id = record.get("case_id")
                name = record.get("name")
                ctx = {"file": display, "sheet": sheet, "row": row,
                       "case": f"{'' if case_id is None else str(case_id).strip()}-"
                               f"{'' if name is None else str(name).strip()}"}

                if _is_blank(case_id) and _is_blank(name) and _is_blank(record.get("method")):
                    # 整行只有备注 / 格式残留：框架仍会把它当用例收集并在执行时失败，这里只提示
                    collector.warn("API-ROW", "该行 case_id / name / method 均为空（不会被执行，建议删除或补齐）", **ctx)
                    continue
                if _is_blank(case_id):
                    collector.error("API-ID", "case_id 为空", **ctx)
                else:
                    key = str(case_id).strip()
                    if key in seen_ids:
                        # 结果按 (sheet, 行) 回写，id 重复本身不影响执行，只影响排查定位
                        collector.warn("API-ID", f"case_id [{key}] 重复（首次出现在 {seen_ids[key]}）", **ctx)
                    else:
                        seen_ids[key] = f"{sheet} 第{row}行"
                if _is_blank(name):
                    collector.error("API-NAME", "name 为空（Allure 标题、接口端选择都依赖它）", **ctx)

                method = _api_method_check(collector, record.get("method"), ctx)
                url = _as_text(record.get("url")).strip()
                data_raw = record.get("data")
                validata = record.get("validata")

                # ---- 各 method 的前置要求 ----
                if method in NO_URL_METHODS:
                    if method == "editexcel":
                        try:
                            cfg = json.loads(str(data_raw)) if not _is_blank(data_raw) else None
                        except (TypeError, ValueError):
                            cfg = None
                            collector.error("API-EDITEXCEL", "editexcel 的 data 必须是 JSON 对象（file / cells 或 index_cells）", **ctx)
                        if isinstance(cfg, dict):
                            if not str(cfg.get("file") or "").strip():
                                collector.error("API-EDITEXCEL", "editexcel 缺少 file（待编辑的 xlsx 路径）", **ctx)
                            if not cfg.get("cells") and not cfg.get("index_cells"):
                                collector.error("API-EDITEXCEL", "editexcel 缺少 cells 或 index_cells", **ctx)
                            target = cfg.get("file")
                            if isinstance(target, str) and target and "${" not in target:
                                full = target if os.path.isabs(target) else os.path.join(paths.API_ROOT, target)
                                if not os.path.isfile(full) and not os.path.isfile(paths.resolve(target)):
                                    collector.warn("API-EDITEXCEL", f"待编辑文件不存在：{target}", **ctx)
                    if _is_blank(data_raw):
                        collector.error("API-DB", f"{method} 未填写 SQL（data 列为空）", **ctx)
                elif method == "download":
                    if not url:
                        collector.error("API-URL", "download 未填写 url", **ctx)
                    data_obj = _json_obj(data_raw)
                    if isinstance(data_obj, dict):
                        unknown = set(data_obj) - {"dir", "var", "params"}
                        if unknown:
                            collector.warn("API-DOWNLOAD", f"download 的 data 只认 dir/var/params，未知键：{'、'.join(unknown)}",
                                           **ctx)
                        # download 的 var 是本用例产出的变量（下载文件路径），后续用例可直接引用
                        download_var = data_obj.get("var")
                        if download_var and str(download_var).strip():
                            available.add(str(download_var).strip())
                elif method == "payrollconfirm":
                    if _is_blank(data_raw):
                        collector.error("API-CONFIRM", "payrollconfirm 的 data 为空，无法拼装 excelDistrictDataMap/countDataMap",
                                        **ctx)
                    elif _json_obj(data_raw) is None:
                        collector.error("API-CONFIRM", "payrollconfirm 的 data 必须是 JSON 对象，当前无法解析", **ctx)
                elif method:
                    if not url:
                        collector.error("API-URL", "url 为空（请求会打到站点根路径）", **ctx)
                    if _is_blank(record.get("headers")):
                        collector.warn("API-HEADERS", "headers 为空，多数接口会返回 401/110106", **ctx)

                # ---- pkgquery 会写入薪资包变量（pkg_id / pkg_code / ...），后续用例可直接引用 ----
                if method == "pkgquery":
                    try:
                        from api.common.payroll_package import VARIABLE_FIELDS
                        available.update(VARIABLE_FIELDS.keys())
                    except Exception:      # noqa: BLE001
                        available.update({"pkg_id", "pkg_code", "pkg_status"})

                # ---- 断言 / 提取 / 重试 ----
                _api_validata_check(collector, method, validata, ctx)
                _api_extract_check(collector, record.get("extract"), ctx, available)
                _api_retry_check(collector, record.get("retry"), ctx)

                # ---- 变量引用 ----
                referenced = []
                for fname in ("name", "url", "data", "headers", "validata"):
                    text = _as_text(record.get(fname))
                    found, unclosed = scan_variables(text)
                    if unclosed:
                        collector.error("API-VAR", f"{fname} 列的 ${{ 未闭合：{text[-40:]}", **ctx)
                    for var in found:
                        if not var:
                            collector.error("API-VAR", f"{fname} 列存在空变量引用 ${{}}", **ctx)
                        elif var not in available:
                            referenced.append((fname, var))
                for fname, var in referenced[:6]:
                    collector.error("API-VAR",
                                    f"{fname} 列引用变量 ${{{var}}} 未定义（不在 all.yaml / .env / 前序 extract 中）"
                                    f"{_suggest(var, available)}", **ctx)
                if len(referenced) > 6:
                    collector.warn("API-VAR", f"还有 {len(referenced) - 6} 个未定义变量未逐条列出", **ctx)
    finally:
        wb.close()
    return display, total


# ============================================================================
# UI 侧：YAML 用例
# ============================================================================


def ui_project_settings(project):
    from ui.config.settings import Settings
    os.environ["UI_PROJECT"] = project
    return Settings()


def ui_settings_for(label):
    """按项目名取 UI 配置；--file 直接指定 yaml 时 label 不是项目名，回落到默认项目，
    只借用它的定位器 / 页面配置，不改 .env 里的项目名。
    """
    from ui.config.settings import Settings
    projects = list(Settings().PROJECT_CONFIGS.keys())
    if label in projects:
        return ui_project_settings(label)
    fallback = os.getenv("UI_PROJECT") or projects[0]
    if fallback not in projects:
        fallback = projects[0]
    return ui_project_settings(fallback)


def _load_yaml(path):
    import yaml
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def lint_ui_file(path, settings, collector):
    display = os.path.relpath(path, ROOT)
    try:
        data = _load_yaml(path)
    except Exception as e:                # noqa: BLE001
        collector.error("UI-FILE", f"无法解析 YAML：{e}", file=display)
        return display, 0

    if not isinstance(data, dict) or "test_cases" not in data:
        collector.error("UI-FILE", "根节点缺少 test_cases（执行时加载到 0 条用例）", file=display)
        return display, 0
    cases = data.get("test_cases") or []
    if not isinstance(cases, list):
        collector.error("UI-FILE", "test_cases 必须是列表", file=display)
        return display, 0
    if not cases:
        collector.warn("UI-FILE", "test_cases 为空，不会执行任何用例", file=display)

    # 定位器：{页面名: {元素名: {by, value}}}
    locators = {}
    try:
        locators = _load_yaml(settings.ELEMENT_LOCATORS) or {}
    except Exception as e:                # noqa: BLE001
        collector.error("UI-LOCATOR", f"无法解析定位器文件 {settings.ELEMENT_LOCATORS}：{e}", file=display)

    page_names = settings.PAGE_NAME if isinstance(settings.PAGE_NAME, (list, tuple)) else [settings.PAGE_NAME]
    known_pages = set(locators.keys()) | set(settings.PAGE_URLS.keys())
    # 框架的元素查找是「全局扫描所有页面节点」（base_page.find_element_page），
    # 所以元素只要在该定位器文件任意节点下存在就能用，不能只看用例的 page 节点。
    element_index = {}
    for pname, elements in locators.items():
        if isinstance(elements, dict):
            for ename in elements:
                element_index.setdefault(ename, pname)
    available_vars = set(UI_PRELOAD_VARS)
    seen_ids = {}

    for case in cases:
        if not isinstance(case, dict):
            collector.error("UI-CASE", f"用例节点不是字典：{case!r}", file=display)
            continue
        case_id = case.get("id")
        case_name = case.get("name")
        ctx = {"file": display, "case": f"{'' if case_id is None else case_id}-{'' if case_name is None else case_name}"}

        if _is_blank(case_id):
            collector.error("UI-ID", "用例缺少 id", **ctx)
        else:
            key = str(case_id).strip()
            if key in seen_ids:
                collector.error("UI-ID", f"用例 id [{key}] 重复", **ctx)
            seen_ids[key] = True
        if _is_blank(case_name):
            collector.error("UI-NAME", "用例缺少 name", **ctx)

        page = case.get("page")
        if _is_blank(page):
            collector.error("UI-PAGE", "用例缺少 page（执行时取页面对象会 KeyError）", **ctx)
        else:
            page = str(page).strip()
            if page not in known_pages:
                collector.error("UI-PAGE", f"page [{page}] 未在定位器文件或 PAGE_URLS 中定义"
                                           f"{_suggest(page, known_pages)}", **ctx)
            if page_names and page not in page_names:
                collector.warn("UI-PAGE", f"page [{page}] 不在当前项目的 PAGE_NAME {page_names} 内（可能不会被导航）", **ctx)

        steps = case.get("steps")
        if not isinstance(steps, list) or not steps:
            collector.error("UI-STEPS", "steps 为空或不是列表", **ctx)
            continue

        page_locators = locators.get(str(page).strip(), {}) if page else {}
        if page and str(page).strip() in locators and not isinstance(page_locators, dict):
            collector.error("UI-LOCATOR", f"定位器文件里 page [{page}] 节点不是字典", **ctx)
            page_locators = {}

        for index, step in enumerate(steps, start=1):
            if not isinstance(step, dict):
                collector.error("UI-STEP", f"第 {index} 个步骤不是字典：{step!r}", **ctx)
                continue
            step_name = step.get("step_name")
            element = step.get("element")
            action = step.get("action")
            data = step.get("data")
            expected = step.get("expected")
            step_ctx = dict(ctx)
            step_ctx["case"] = f"{ctx['case']}" if ctx["case"] else ""
            label = f"步骤{index}「{'' if step_name is None else step_name}」"

            if _is_blank(step_name):
                collector.error("UI-STEP", f"{label} 缺少 step_name", **step_ctx)
            if _is_blank(action):
                collector.error("UI-STEP", f"{label} 缺少 action", **step_ctx)
                continue
            action = str(action).strip()
            if action not in UI_ACTIONS:
                collector.error("UI-ACTION", f"{label} action [{action}] 非法"
                                             f"{_suggest(action, UI_ACTIONS)}", **step_ctx)
                continue

            # 占位符类型守卫（与 executor._guard_field 一致）
            for fname, value in (("element", element), ("data", data), ("expected", expected)):
                if isinstance(value, (dict, list)):
                    collector.error("UI-YAML-TYPE",
                                    f"{label} 的 {fname} 被 YAML 解析成 {type(value).__name__}：{value!r}"
                                    f"（占位符必须加引号，如 {fname}: '{{username}}'）", **step_ctx)

            # 元素必填性 + 存在性
            if action in UI_NO_ELEMENT_ACTIONS:
                pass                      # 这些动作不使用 element，配了也只是被忽略，不占噪声
            elif _is_blank(element):
                collector.error("UI-ELEMENT", f"{label} 的 action={action} 必须配置 element", **step_ctx)
            else:
                element_text = str(element)
                if "{" in element_text:
                    collector.warn("UI-ELEMENT", f"{label} element 含变量 [{element_text}]，跳过存在性检查", **step_ctx)
                elif element_index:
                    if element_text not in element_index:
                        collector.error("UI-ELEMENT",
                                        f"{label} element [{element_text}] 在 "
                                        f"{os.path.basename(settings.ELEMENT_LOCATORS)} 中不存在"
                                        f"{_suggest(element_text, element_index)}", **step_ctx)
                    else:
                        owner = locators.get(element_index[element_text]) or {}
                        node = owner.get(element_text)
                        if isinstance(node, dict):
                            for key in ("by", "value"):
                                if key not in node:
                                    collector.error("UI-LOCATOR", f"{label} 元素 [{element_text}] 定位器缺少 {key} 字段",
                                                    **step_ctx)

            # action 专属规则
            if action == "check_exists":
                if str(data).strip() not in ("存在", "不存在"):
                    collector.error("UI-ACTION-DATA",
                                    f"{label} check_exists 的 data 只能填 '存在' 或 '不存在'，当前 {data!r}", **step_ctx)
            elif action == "wait":
                try:
                    int(str(data).strip())
                except (TypeError, ValueError):
                    collector.error("UI-ACTION-DATA", f"{label} wait 的 data 必须是秒数（整数），当前 {data!r}", **step_ctx)
            elif action == "edit_excel":
                if _is_blank(expected):
                    collector.error("UI-ACTION-DATA", f"{label} edit_excel 需要在 expected 里写填写配置 JSON", **step_ctx)
                else:
                    try:
                        json.loads(str(expected))
                    except (TypeError, ValueError):
                        collector.error("UI-ACTION-DATA", f"{label} edit_excel 的 expected 不是合法 JSON", **step_ctx)
                if _is_blank(data):
                    collector.error("UI-ACTION-DATA", f"{label} edit_excel 的 data 应为文件路径", **step_ctx)
            elif action == "upload":
                if _is_blank(data):
                    collector.error("UI-ACTION-DATA", f"{label} upload 的 data 应为本地文件路径", **step_ctx)
            elif action == "download":
                # data = 保存的文件名（可含变量，如 {settlement_package_code}.xlsx）
                if _is_blank(data):
                    collector.error("UI-ACTION-DATA", f"{label} download 的 data 应为保存的文件名", **step_ctx)
            elif action in ("sql", "sql_update"):
                if _is_blank(data):
                    collector.error("UI-ACTION-DATA", f"{label} {action} 的 data 应写 SQL", **step_ctx)
            elif action in ("save_text", "save_value"):
                if _is_blank(data):
                    collector.error("UI-ACTION-DATA", f"{label} {action} 的 data 应为变量名", **step_ctx)
                elif not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", str(data).strip()):
                    collector.error("UI-ACTION-DATA",
                                    f"{label} {action} 的 data 应是变量名（字母/下划线开头），当前 {data!r}", **step_ctx)
            elif action in ("input", "check_text", "check_value", "wait_text", "wait_value", "submit"):
                if _is_blank(data):
                    collector.warn("UI-ACTION-DATA", f"{label} {action} 的 data 为空，该步骤可能什么都没校验", **step_ctx)

            # 变量引用（{变量}），按执行顺序累积已定义的变量
            scan_text = " ".join(_as_text(v) for v in (step_name, element, data, expected))
            # ① 接口侧的 ${var} 写法在 UI 用例里不生效（VariableStore 只替换 {var}），会残留成 "$"
            dollar_vars = re.findall(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}", scan_text)
            for var in dollar_vars:
                collector.error("UI-VAR-SYNTAX",
                                f"{label} 用了接口侧写法 ${{{var}}}（UI 用例只认 {{{var}}}，执行时会残留 $ 并拼进输入）",
                                **step_ctx)
            scan_text = re.sub(r"\$\{[A-Za-z_][A-Za-z0-9_]*\}", " ", scan_text)
            # ② 普通 {var}
            for var in UI_VAR_RE.findall(scan_text):
                if var not in available_vars:
                    collector.error("UI-VAR",
                                    f"{label} 引用变量 {{{var}}} 未定义（不在 preload 变量或前序 save_text/save_value/download 中）"
                                    f"{_suggest(var, available_vars)}", **step_ctx)
            if action in ("save_text", "save_value") and not _is_blank(data):
                available_vars.add(str(data).strip())

        # 用例内复用：前面用例 save 的变量对后面用例可见（VariableStore 进程级共享）
    return display, len(cases)


# ============================================================================
# 入口
# ============================================================================


def collect_targets(args):
    """返回 [(suite, 标识, 文件路径)]"""
    targets = []
    for f in args.file:
        full = f if os.path.isabs(f) else os.path.join(os.getcwd(), f)
        if not os.path.isfile(full):
            print(f"[lint] 文件不存在：{f}", file=sys.stderr)
            continue
        suite = "api" if full.lower().endswith((".xlsx", ".xlsm")) else "ui"
        targets.append((suite, os.path.basename(full), full))
    if targets:
        return targets

    if args.suite in ("api", "all"):
        mapping = api_projects()
        if args.project:
            chosen = {k: v for k, v in mapping.items() if k in args.project}
            unknown = [p for p in args.project if p not in mapping]
            for p in unknown:
                print(f"[lint] 接口侧没有项目 {p!r}（可选：{'、'.join(mapping) or '无'}）", file=sys.stderr)
        else:
            chosen = mapping
        for project, rel in chosen.items():
            targets.append(("api", project, paths.resolve(rel, paths.API_ROOT)))
        # 未登记但符合 test_*.xlsx 命名的用例文件也一起检查，避免新写的用例漏检
        if not args.project:
            registered = {os.path.normcase(paths.resolve(v, paths.API_ROOT)) for v in mapping.values()}
            for f in sorted(glob.glob(os.path.join(paths.API_ROOT, "testcase", "test_*.xlsx"))):
                if os.path.normcase(f) not in registered:
                    targets.append(("api", os.path.basename(f), f))

    if args.suite in ("ui", "all"):
        from ui.config.settings import Settings
        # 用一个默认实例读项目名（构造 Settings 只是读配置，不启动浏览器、不连数据库）
        projects = list(Settings().PROJECT_CONFIGS.keys())
        if args.project:
            chosen = [p for p in args.project if p in projects]
            for p in [p for p in args.project if p not in projects]:
                print(f"[lint] UI 侧没有项目 {p!r}（可选：{'、'.join(projects)}）", file=sys.stderr)
        else:
            chosen = projects
        for project in chosen:
            try:
                settings = ui_project_settings(project)
            except SystemExit as e:
                print(f"[lint] 加载 UI 项目 {project} 配置失败：{e}", file=sys.stderr)
                continue
            targets.append(("ui", project, settings.TESTCASES))
    return targets


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="用例静态检查（执行前的第一道机器初审）",
        formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    parser.add_argument("--suite", choices=["api", "ui", "all"], default="all", help="检查哪一侧，默认 all")
    parser.add_argument("--project", action="append", default=[], help="只查指定项目（可重复）")
    parser.add_argument("--file", action="append", default=[], help="只查指定用例文件（可重复）")
    parser.add_argument("--strict", action="store_true", help="警告也视为失败（CI 门禁用）")
    parser.add_argument("--format", choices=["text", "json"], default="text", help="输出格式")
    args = parser.parse_args(argv)

    # 让配置层能安全导入：接口侧不强制要求项目名
    os.environ.setdefault("TEST_SUITE", "")
    if not os.environ.get("TEST_SUITE"):
        os.environ["TEST_SUITE"] = ""
    os.environ.pop("API_PROJECT", None)

    collector = Collector()
    targets = collect_targets(args)
    if not targets:
        print("[lint] 没有找到待检查的用例文件", file=sys.stderr)
        return 2

    api_available = api_globals() if any(t[0] == "api" for t in targets) else set()

    for suite, label, path in targets:
        if not os.path.isfile(path):
            collector.error("FILE", f"用例文件不存在：{path}", file=label)
            collector.files.append((label, 0))
            continue
        if suite == "api":
            display, total = lint_api_file(path, collector, set(api_available))
        else:
            try:
                settings = ui_settings_for(label)
            except SystemExit as e:
                collector.error("CONFIG", f"项目配置不可用：{e}", file=label)
                collector.files.append((label, 0))
                continue
            display, total = lint_ui_file(path, settings, collector)
        collector.files.append((display, total))

    # ---------------- 输出 ----------------
    if args.format == "json":
        print(json.dumps({
            "files": [{"name": n, "cases": c} for n, c in collector.files],
            "summary": {"errors": collector.errors, "warnings": collector.warnings},
            "issues": [i.as_dict() for i in collector.issues],
        }, ensure_ascii=False, indent=2))
    else:
        current = None
        for issue in collector.issues:
            if issue.file != current and issue.file:
                current = issue.file
                cases = dict(collector.files).get(current, 0)
                e, w = collector.count(ERROR, current), collector.count(WARN, current)
                flag = "OK  " if e == 0 else "FAIL"
                print(f"\n[{flag}] {current}  （{cases} 条用例，{e} 错误 {w} 警告）")
            print("   " + str(issue))

        print("\n" + "=" * 74)
        for name, count in collector.files:
            e, w = collector.count(ERROR, name), collector.count(WARN, name)
            print(f"  {name:<58} {count:>4} 条  E{e} W{w}")
        print("=" * 74)
        verdict = "不通过（存在阻断执行的错误）" if collector.errors else \
            ("通过（仅警告）" if collector.warnings else "全部通过")
        print(f"  合计：{len(collector.files)} 个文件，"
              f"{sum(c for _, c in collector.files)} 条用例，"
              f"{collector.errors} 错误 / {collector.warnings} 警告 → {verdict}")

    if collector.errors or (args.strict and collector.warnings):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
