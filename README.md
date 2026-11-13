# autotest —— 接口 + UI 自动化统一框架

一套配置、一个入口、一个报告目录，同时驱动两个用例集：

| 用例集 | 目录 | 驱动方式 | 用例数据 | 执行入口 |
| --- | --- | --- | --- | --- |
| 接口自动化 `api` | `api/` | Excel 驱动（pytest parametrize） | `api/testcase/*.xlsx` | `api/test_file.py` |
| UI 自动化 `ui` | `ui/` | YAML 驱动（Playwright） | `ui/testcases/**/*.yaml` | `ui/test_from_yaml.py` |

> 用 AI 执行测试时：**先读根目录 [`AGENTS.md`](AGENTS.md)**（需求拆分→用例→执行→提单的总流程），提单前再读 [`PROMPT_bug_filing.md`](PROMPT_bug_filing.md)。

共用：`.env` 配置、日志（`core/logger.py`）、报告目录（`reports/`）、Allure 结果、pytest 根配置、统一入口 `run.py`。
两个用例集都用 **数据文件**（Excel / YAML）描述用例，所以新增用例通常只需要写数据文件，不用写代码。

## 目录结构

```
autotest/
├─ run.py                    统一入口：api / ui / all / lint / --list
├─ conftest.py               pytest 根配置（sys.path、报告目录、用例集校验）
├─ pytest.ini                两个用例集共用的 pytest 配置
├─ AGENTS.md                 AI 执行手册（从需求拆分到提单的总流程，开工先读）
├─ PROMPT_bug_filing.md      禅道提单硬约束提示词
├─ .env / .env.example       统一配置（数据库、token、企微 Webhook、默认项目）
├─ requirements.txt
├─ core/                     公共层
│   ├─ paths.py              统一路径（全部绝对化，任意工作目录可执行）
│   ├─ env.py                统一 .env 加载（系统环境变量优先）
│   └─ logger.py             日志工厂（API_/UI_ 前缀 → reports/logs）
├─ docs/
│   └─ 用例编写模板.md        列定义 / 动作表 / 命名规范 / 设计口径（模板用法说明）
├─ tools/
│   ├─ lint_cases.py         用例静态检查（执行前的机器初审）
│   ├─ selftest_lint.py      lint 自身的回归自测（17 类埋错，验证规则是否生效）
│   └─ ui_capture.py         现场采集：登录 → 菜单导航 → 导出候选定位器/HTML/截图
├─ api/                      接口用例集
│   ├─ common/               请求、断言、变量、Excel、数据库、重试、薪资包工具
│   │   ├─ payroll_util.py     薪资包/结算包指标与确认体构建
│   │   └─ payroll_package.py  薪资包管理查询方法（本次新增）
│   ├─ config/setting.py     项目注册表 TEST_FLIELOADS + 路径/超时/DB 配置
│   ├─ testcase/             用例 Excel（数据准备 / 测试执行 / 数据清理）
│   │   └─ test_TEMPLATE_api.xlsx   接口用例模板（可整表复制，lint 干净）
│   ├─ variable/             all.yaml（全局变量）+ extract.yaml（运行期临时变量，不入库）
│   ├─ conftest.py           会话级夹具（结果文件、Allure、企微通知、DB 关闭）
│   └─ test_file.py          Excel 用例入口
├─ ui/                       UI 用例集
│   ├─ config/
│   │   ├─ settings.py       项目注册表 PROJECT_CONFIGS + 页面/URL/登录态配置
│   │   └─ locators/         元素定位器 YAML（按项目一份）
│   ├─ pages/                页面对象：base_page / gsr_admin_page / scan_login_page / payroll_package_page
│   ├─ utils/                浏览器、执行器、元素定位、YAML、变量、企业微信
│   ├─ testcases/            YAML 用例 + 附件（_TEMPLATE_ui_case.yaml 为模板）
│   ├─ conftest.py           browser 会话级夹具
│   └─ test_from_yaml.py     YAML 用例入口
└─ reports/                  统一产物（不进 git）
    ├─ logs/ logs_error/     API_log_*.log / UI_log_*.log
    ├─ results/api|ui/       执行结果文件（Excel 副本 / YAML 结果）
    ├─ downloads/            接口下载文件 + 浏览器下载
    ├─ screenshots/          UI 失败截图
    ├─ auth/                 登录态（token 模式下为 token cookie 的快照）
    ├─ allure-results/       Allure 原始结果
    └─ _probe/               现场采集产物（HTML / 截图 / 候选定位器）
```

---

## 1. 快速开始

```powershell
pip install -r requirements.txt
python -m playwright install chromium      # UI 用例集首次需要

python run.py --list                       # 看有哪些用例集/项目
python run.py lint                         # 执行前静态检查（秒级）
python run.py api 薪资包管理查询             # 跑接口用例
python run.py ui  薪资包管理查询 --headless  # 跑 UI 用例（免扫码）
```

### `.env` 配置项

优先级：**系统环境变量 > `.env` > 代码默认值**。

| 键 | 说明 |
| --- | --- |
| `ENV` | 环境：`测试环境` / `预生产环境` / `生产环境`（默认测试环境） |
| `API_PROJECT` | 接口用例默认项目（PyCharm 直接运行时生效） |
| `UI_PROJECT` | UI 用例默认项目 |
| `CURRENT_PROJECT` | 兼容旧写法（两个用例集都读不到上面两项时兜底） |
| `ACCESS_TOKEN_ADMIN` | **管理端 token**：接口 `Authorization` + UI 免扫码登录都用它（浏览器 `GSR-Token` cookie 的值） |
| `USER_TOKEN` | 员工端 token（`all.yaml` 的 `headers_user` 用它） |
| `UI_LOGIN_BY_TOKEN` | UI 是否用 token 免扫码（默认 `true`；`false` 则回落到扫码/cookie 复用） |
| `DB_HOST/PORT/USER/PASSWORD/NAME` | 数据库（`sql` / `db_select` / `db_update` 类用例需要） |
| `HTTP_TIMEOUT` | 接口默认超时（秒） |
| `WECOM_WEBHOOK` / `WECOM_ENABLE` | 企业微信群机器人（执行结果 + 登录二维码推送） |
| `LOGIN_USER` / `PASSWORD` | 仅 ddddocr 账号密码登录旧链路用（扫码/token 登录不需要） |

---

## 2. 执行用例

| 命令 | 说明 |
| --- | --- |
| `python run.py --list` | 列出两个用例集的所有项目名 |
| `python run.py lint [参数]` | 用例静态检查（见第 6 节） |
| `python run.py api <项目名>` | 只跑接口用例集 |
| `python run.py ui <项目名>` | 只跑 UI 用例集 |
| `python run.py all` | 两个用例集各跑 `.env` 里的默认项目 |

常用附加参数：

```powershell
python run.py api 审批流员工标签 -k 标签       # 只跑名称匹配的用例
python run.py api 薪资包结算 --report          # 跑完生成 allure html
python run.py ui 薪资包管理查询 --headless      # 无头（服务器/后台跑）
python run.py ui 薪资包管理查询 --headed        # 有头（调试用，能看到点击过程）
```

退出码：`0` 全部通过；`1` 有用例失败；`2` 参数/配置错误。

---

## 3. PyCharm 直接运行

三种方式，按需选：

| 方式 | 做法 | 跑哪个项目 |
| --- | --- | --- |
| 推荐：终端 | `python run.py ui 薪资包管理查询 --headless` | 命令行指定的项目 |
| 右键运行 | 右键 `api/test_file.py` 或 `ui/test_from_yaml.py` → Run | `.env` 里的 `API_PROJECT` / `UI_PROJECT` |
| pytest 配置 | Test Runner 选 pytest，`Additional Arguments` 里加 `-k xxx` | 同上 |

两个必须知道的点：

1. **Test Runner 要选 pytest**（Settings → Tools → Python Integrated Tools → Default test runner = pytest），否则默认的 unittest 模板识别不到 `parametrize`，会显示 0 个用例。
2. `api/conftest.py`、`ui/conftest.py` 已带 sys.path 引导，所以**在 `api/`、`ui/` 子目录下右键运行也不会 import 失败**。
   实测：`api/` 下收集 161 条、`ui/` 下收集 5 条、`ui/` 实跑 3 条 19.92s 全过。

---

## 4. 当前用例清单

### 接口用例集（`api/testcase/`）

| 项目名 | 用例文件 | 内容 |
| --- | --- | --- |
| 假勤 | `test_approval.xlsx` | 假勤审批基础链路 |
| 调试 | `test_test.xlsx` | 调试用（含占位行，lint 会告警） |
| payroll | `test_payroll.xlsx` | 薪资包基础 |
| 审批流或签自动通过 | `test_approval_auto_approved.xlsx` | 或签自动通过 |
| 审批流或签矩阵 | `test_approval_ouqian_matrix.xlsx` | 或签矩阵 |
| 报销自动审批 | `test_reimbursement_auto_approval.xlsx` | 报销自动审批 |
| 报销审批人为空 | `test_reimbursement_empty_approver.xlsx` | 审批人为空策略 |
| 假勤审批人为空 | `test_leave_empty_approver.xlsx` | 假勤侧审批人为空 |
| 审批流员工标签 | `test_approval_employee_tag.xlsx` | 员工标签条件（Story1） |
| 薪资包结算 | `test_payroll_salary_package_offcycle.xlsx` | 薪资包发起结算全链路 |
| **薪资包管理查询** | `test_payroll_package_query.xlsx` | Payroll→算薪→薪资包管理：按薪资包ID查询（10 条，含 `pkgquery` 方法与变量传递） |

### UI 用例集（`ui/testcases/`）

| 项目名 | 用例文件 | 定位器文件 | 内容 |
| --- | --- | --- | --- |
| 招聘平台新建岗位 | `pt_new_position/pt_testcases.yaml` | `new_position_element_locators.yaml` | 非 EOR 岗位全流程 |
| 招聘平台新建编制 | `pt_new_preparation/new_preparation.yaml` | `gsr_admin_page.yaml` | 编制流程 |
| **薪资包管理查询** | `payroll_package/package_query.yaml` | `payroll_package_management.yaml` | 按薪资包ID查询：命中字段校验 / 不存在为空 / 重置恢复（3 条） |
| 薪资结算包收款包链路 | `eor_salary_ettlement/salary_payment_collection_v2.yaml` | `gsr_admin_page_management.yaml` | 结算包收款包链路 |

> 项目「招聘平台新建岗位-维护版」已**临时停用**：它指向的 `ui/testcases/pt_new_position_v2/pt_testcases_v2.yaml` 不存在（lint 会报错），补回该文件后取消 `ui/config/settings.py` 里的注释即可恢复。
> 用例总数以 `python run.py lint` 的统计为准（当前 16 个文件、817 条、0 错误）。

---

## 5. 登录与鉴权

**一份 `.env` 就够了**，管理端"接口 + UI"共用同一个 token。

| 场景 | 用什么 |
| --- | --- |
| 接口用例（管理端） | `all.yaml` 的 `headers_admin` → `${access_token_admin}` → `.env` 的 `ACCESS_TOKEN_ADMIN` |
| 接口用例（员工端） | `all.yaml` 的 `headers_user` → `${user_token}` → `.env` 的 `USER_TOKEN` |
| UI 用例（管理端） | `ui/utils/browser.py` 把 `ACCESS_TOKEN_ADMIN` 注入成 `GSR-Token` cookie，**免扫码** |

### token 获取方式

浏览器登录管理端 → DevTools → Application → Cookies → 复制 `GSR-Token` 的值 → 粘贴到 `.env` 的 `ACCESS_TOKEN_ADMIN`。
约 **2 小时过期**；过期后接口用例会 401/110106，UI 会自动回落到扫码流程。

### 三个实测踩过的坑（已在代码里处理）

1. **token 模式不能加载旧登录态**：若同时加载 `reports/auth/*.json`，请求会带上过期会话的 cookie，服务端按旧会话鉴权 → `110106 没有访问权限`。现在 token 模式直接不加载旧文件。
2. **新扫码的会话可能缺权限**：刚扫码建立的会话调 `payrollSalaryPackage/list` 会 110106，而 `.env` 里较早的 token 权限正常 —— 说明权限缓存/角色同步有问题（建议提单）。
3. **扫码兜底保留**：token 为空或失效时，仍走原来的企业微信扫码（有头等本地扫码 / 无头推送二维码到企微群）。关闭免扫码：`UI_LOGIN_BY_TOKEN=false`。

---

## 6. 用例静态检查（lint）

执行前跑一遍，把"一跑就崩 / 静默空转"的格式与引用错误挡在执行之前。不连数据库、不连业务系统、不需要 token。

```powershell
python run.py lint                         # 全查（接口 + 所有 UI 项目）
python run.py lint --suite api             # 只查接口
python run.py lint --project 薪资包管理查询  # 只查某个项目（可重复）
python run.py lint --file api/testcase/x.xlsx
python run.py lint --strict                # 警告也算失败（CI 门禁）
python run.py lint --format json           # 机器可读输出
python tools/selftest_lint.py              # lint 自身的回归自测
```

| 侧 | 检查内容 |
| --- | --- |
| 接口 | sheet 列数 / 必需列 / 列头重复；`method` 合法性；`db_select`·`db_update` 的 SQL 与断言写法（含"SET autocommit 写进断言列"这类坑）；`editexcel` 必填项；`download` 的 data 结构；`retry` 取值；`validata` 的 JSON / jsonpath 格式；`extract` 格式；`${变量}` 是否在 `all.yaml` / `.env` / 前序 `extract` / `download.var` / `pkgquery` 产出的变量里 |
| UI | `action` 合法性；`element` 是否存在于定位器文件（带相近名建议）；`check_exists` 只允许 `存在`/`不存在`；`wait` 必须是整数；`edit_excel` 的 expected 必须为 JSON；`save_text`/`save_value` 的 data 必须是变量名；占位符没加引号被 YAML 解析成 dict；`${var}` 与 `{var}` 混用；`{变量}` 未定义；用例 id 重复；`page` 合法性 |

- 合法动作集合是从 `api/common/executor.py`、`api/common/request_util.py`、`ui/utils/executor.py` **源码反射**出来的，动作增删后自动跟随。
- 退出码：有错误 = `1`（`--strict` 时警告也算），否则 `0`。
- 当前全量结果：**817 条用例 / 6 错误 / 21 警告**。6 个错误都是 UI 侧存量问题（见第 10 节），接口侧 0 错误。

---

## 7. 现场采集（找元素）

```powershell
# 按菜单路径导航（支持多级），导出候选定位器 + 截图 + 完整 HTML
python tools/ui_capture.py --menu "Payroll/算薪/薪资包管理" --headless

# 直接打开指定 URL
python tools/ui_capture.py --url https://test-admin.gsrtech.com/center/payroll/payrollSalary/packageManagement

# 顺带验证按关键字搜索的结果
python tools/ui_capture.py --url <URL> --query SAL-20261112-0001
```

产物在 `--out` 目录（默认 `reports/_probe/`）：

- `candidates_target.json`：输入框（含 form-item 标签）、按钮、表头、首行单元格、菜单文本
- `page_target.html`：完整 DOM（离线翻结构）
- `page_target.png`：整页截图

登录态：有 `ACCESS_TOKEN_ADMIN` 就免扫码；否则复用 `reports/auth/*.json`；都失效会在有头浏览器里等你扫码（`--wait` 秒，默认 300）。

> 采集工具只做"采集与导出"，**不会自动改定位器 YAML** —— 这一步人工确认后再写，避免自动生成错定位器。

---

## 8. 框架方法速查

### 接口：`api/common/payroll_package.py`

```python
from api.common.payroll_package import (
    query_salary_packages, get_salary_package, require_salary_package,
    package_variables, assert_row_fields,
)

query_salary_packages(payPagType="1", pageSize=5)   # 任意条件 + 分页，返回原始 {total, rows}
row = get_salary_package("SAL-20261112-0001")       # 按薪资包ID精确查，查不到返回 None
require_salary_package("SAL-20261112-0001")         # 查不到直接断言失败
package_variables(row)                              # → {pkg_id, pkg_code, pkg_status, pkg_country, ...}
assert_row_fields(row, "pkg_status=0,pkg_country=Canada")
```

对应接口：`GET /api/center/payrollSalaryPackage/list`（`Authorization: Bearer <ACCESS_TOKEN_ADMIN>`）。

### 接口用例动作：`method: pkgquery`

Excel 里一行就能完成"查询 + 写变量 + 字段断言"：

| 列 | 值 |
| --- | --- |
| method | `pkgquery` |
| data | `{"code": "SAL-20261112-0001"}`（`code` 之外可加 `filters` 或直接写其他查询字段） |
| validata | `pkg_code=SAL-20261112-0001,pkg_status=0,pkg_country=Canada` |

查询成功后会把 `pkg_id / pkg_code / pkg_type / pkg_supplier / pkg_country / pkg_service_month / pkg_employee_count / pkg_status / pkg_settle_code / pkg_source / pkg_lock_time` 写进变量，后续用例可直接 `${pkg_id}` 引用。

### UI：`ui/pages/payroll_package_page.py`

```python
page.open_package_management()                        # 打开薪资包管理页
page.query_by_package_code("SAL-20261112-0001")       # 输入并搜索，等 list 接口返回
page.get_row_by_code("SAL-20261112-0001")             # → {'薪资包ID': ..., '状态': ...}
page.assert_package_row(code, 状态="待发起算薪", **{"国家/地区": "Canada"})
page.assert_empty()                                   # 断言「暂无数据」
page.get_total_text()                                 # 第 1-1 条/总共 1 条
```

页面元素（`ui/config/locators/payroll_package_management.yaml`）：
`#payrollSalaryPackageCode`（薪资包ID）、`#settlementPackageCode`、`#payPagType`、`#supplierId`、`#country`、`#payrollStatus`、搜索/重置按钮（antd 渲染成「搜 索」「重 置」，用 xpath contains 匹配）、表格首行各列、`ant-pagination-total-text`。

---

## 9. 报告与产物

| 产物 | 位置 |
| --- | --- |
| 接口执行结果（源用例副本 + result 列） | `reports/results/api/*.xlsx` |
| UI 执行结果 | `reports/results/ui/*.yaml` |
| Allure 原始结果 | `reports/allure-results/`（`python run.py ... --report` 生成 html 到 `reports/allure-report/`） |
| 日志 | `reports/logs/API_log_*.log`、`UI_log_*.log`；错误单独 `reports/logs_error/` |
| 失败截图 | `reports/screenshots/` |
| 下载文件 | `reports/downloads/` |

---

## 10. 禅道提单（执行结果 → 缺陷）

已接通公司禅道（**开源版 22.6**，`http://172.21.100.100:8101/zentao`），提单模板按提单页实测字段定制：

| 字段 | 取值 | 来源 |
| --- | --- | --- |
| 所属产品 | `1` — GSR OMNI | 禅道唯一产品 |
| 所属模块 | `393` — `/Payroll&结算` | 提单页 URL `moduleID=393` |
| 严重程度 | `3` — 一般 | 提单页默认值 |
| 优先级 | `3` — 中 | 提单页默认值 |
| Bug 类型 | `codeerror` — 代码错误 | 公司存量缺陷绝大多数是它 |
| 影响版本 | `["trunk"]` — 主干 | **必须传数组**，传 `0`/`"0"` 会报"影响版本不能为空" |
| 反馈者 | 登录账号（`Louie.lu`） | 提单页必填项 |
| 当前指派 | `ZENTAO_ASSIGNEE`（默认 `Louie.lu`） | 提单页必填项 |
| 关键词 | `自动化` | 便于日后检索自动化提单 |
| 重现步骤 | HTML 富文本 | 沿用公司模板 `[前置条件]/[步骤]/[结果]/[期望]/[备注]` |

标题风格也对齐公司习惯（`【来源】模块-页面：对象，现象`）：

```
【自动化-测试环境】管理端｜薪资包管理｜按薪资包ID查询：断言项[$.total]失败 期望值: 1 实际值: 0
```

> **提单约束提示词**：仓库根目录 `PROMPT_bug_filing.md` —— 什么该提/不该提、单据必须包含哪些段落、字段取值与禁区、提交前自检清单。可直接整段作为 AI 提示词使用。

### 提单是怎么串起来的（接口 / UI 两个入口共用一套）

| 环节 | 位置 | 说明 |
| --- | --- | --- |
| 接口证据采集 | `api/common/executor.py`（`except` 分支）→ `api/common/evidence.py` | 记录方法 / URL / 请求参数 / HTTP 状态 / 响应 + 断言明细，落盘 `reports/evidence/api_*.json` |
| UI 证据采集 | `ui/utils/executor.py`（`execute_test_case`）→ `ui/utils/evidence.py` | 记录真实步骤 + `/api/` 请求返回（最多 10 条）+ 页面截图 |
| 单据组装 | `tools/evidence_bug.py`（`build_steps_html` / `build_title` / `file_bug`） | **格式只在这里定义**，所有入口共用 |
| 建单 / 改单 / 附件 | `core/zentao.py`（`create_bug` / `update_bug` / `delete_bug`）+ `core/zentao_ui.py`（页面上传附件） | 附件走 REST 会被服务端拒，UI 单的截图用页面表单上传 |
| 入口 | `run.py zentao`（结果驱动）、`tools/evidence_bug.py`（证据包驱动）、`tools/demo_pkg_search.py`（场景模板） | 三者产出格式完全一致 |

```powershell
python run.py zentao                                    # 执行结果 → 草稿
python run.py zentao --submit --yes                      # 执行结果 → 提单
python tools/evidence_bug.py --evidence reports/evidence/xxx.json [--submit]
python tools/evidence_bug.py --evidence reports/evidence/xxx.json --attach-to 9782   # 给已有单补附件
python tools/demo_pkg_search.py --submit                 # 场景模板：搜索不存在的关键字 → 提单
```

实测示例：接口单 [#9784](http://172.21.100.100:8101/zentao/bug-view-9784.html)（无附件，正文含请求参数与接口返回）；
UI 单 [#9782](http://172.21.100.100:8101/zentao/bug-view-9782.html)（带页面截图附件）。

已知限制：该禅道版本把 `<img src="{文件id}.png">` 通过 API 写进步骤后**不会渲染成图片**，
所以截图以附件形式挂在单上、步骤里注明附件名；必须让图片出现在正文时，在禅道里手工插入一次。

### 提单格式（接口单：接口 / 请求参数 / 接口返回 / 期望 / 实际；UI 单：额外带截图）

**所有提单入口都走同一套模板**（`tools/evidence_bug.py`），生成的单据固定包含：

| 段落 | 内容 | 来源 |
| --- | --- | --- |
| `[前置条件]` | 环境、账号、页面/用例文件 | 运行上下文 |
| `[步骤]` | 真实操作步骤（含输入的值、点击的元素） | UI：用例执行步骤；API：请求组装/发送/断言 |
| `[接口]` | 方法 + URL + HTTP 状态 | UI：页面抓包；API：执行器记录 |
| `[请求参数]` | 等宽代码块（JSON 原样） | 同上 |
| `[接口返回]` | 等宽代码块（code/msg/data/total/rows 等关键字段） | 同上 |
| `[期望]` | 人话描述（不是断言原文） | UI：从断言差异还原；API：期望值明细 |
| `[实际]` | 实际现象 | 同上 |
| `[截图]` | 见本单附件：文件名（**仅 UI 单有**） | UI：失败页面截图 |
| `[备注]` | 用例ID、采集时间、页面地址 | 证据包 |

**证据是自动采集的，不需要额外准备：**

| 场景 | 触发 | 产物 |
| --- | --- | --- |
| 接口用例失败 | `api/common/executor.py` 捕获异常 | `reports/evidence/api_*.json`（步骤/接口/请求参数/返回/断言明细）；**接口单不配截图** |
| UI 用例失败 | `ui/utils/executor.py` 捕获异常 | `reports/evidence/*.json`（步骤/接口/截图路径）+ `reports/screenshots/UI失败-*.png` |
| 自定义场景 | `ui/utils/evidence.py` 的 `EvidenceRecorder` | 同上（见 `tools/demo_pkg_search.py`） |

没有证据包时（比如只跑过旧结果文件），提单会从结果文件重建：接口信息取 `url`/`data`/`response` 列。
接口单的正文就是「接口 / 请求参数 / 接口返回 / 期望 / 实际」这套结构；截图只对 UI 单有意义。

### 提单字段对照（我们 → 禅道）

**实际使用的字段**（其余走默认值）

| 我们的概念 | 禅道字段（表单 name / REST key） | 页面标签 | 取值 | `.env` |
| --- | --- | --- | --- | --- |
| 标题 | `title` | Bug标题 | `【自动化-<ENV>】<用例名>：<现象>`（≤255） | — |
| 重现步骤 | `steps` | 重现步骤（`zen-editor` 富文本） | HTML，结构见上表 | — |
| 所属产品 | `product` | 所属产品 | `1` = GSR OMNI | `ZENTAO_PRODUCT` |
| 所属模块 | `module` | 所属模块 | `393` = `/Payroll&结算` | `ZENTAO_MODULE` |
| 严重程度 | `severity` | 严重程度 | `1`~`4`（`3`=一般） | `ZENTAO_SEVERITY` |
| 优先级 | `pri` | 优先级 | `1`~`4`（`3`=中） | `ZENTAO_PRI` |
| 类型 | `type` | Bug类型 | `codeerror`=代码错误 / `codeimprovement`=代码改进 / `others`=其他 | `ZENTAO_TYPE` |
| 影响版本 | `openedBuild[]` | 影响版本 | **必须是数组**：`["trunk"]` = 主干 | `ZENTAO_OPENED_BUILD` |
| 当前指派 | `assignedTo` | 当前指派 | 禅道**账号名**（`Louie.lu`，不是中文姓名） | `ZENTAO_ASSIGNEE` |
| 反馈者 | `feedbackBy` | 反馈者 | 禅道**账号名**，留空默认用登录账号 | `ZENTAO_FEEDBACK` |
| 关键词 | `keywords` | 关键词 | `自动化`（便于检索自动化提单） | `ZENTAO_KEYWORDS` |
| 截图附件 | `files[]` | 附件 | 仅 UI 单；走**页面表单**上传 | — |

**页面还有但当前没用到的字段**（需要时在 `core/zentao.py::create_bug` 的 `extra={...}` 里加即可）

| 页面标签 | 字段 | 说明 |
| --- | --- | --- |
| 截止日期 | `deadline` | 日期 |
| 所属项目 / 所属执行 | `project` / `execution` | 关联迭代，影响"项目权限"校验 |
| 所属计划 | `plan` | 计划 id，`0` = 不关联 |
| 来源用例 / 相关需求 / 相关任务 | `case` / `story` / `task` | id，`0` = 不关联 |
| 通知邮箱 / 抄送给 | `notifyEmail` / `mailto[]` | 抄送账号列表 |
| 浏览器 / 操作系统 | `browser[]` / `os[]` | 多选 |
| 影响版本「所有」/ 当前指派「加载所有」 | `allBuilds` / `allUsers` | 勾选后放开范围 |
| 颜色 | `color` | 缺陷标记色 |

**几个容易踩的取值规则（都实测过）**

1. `openedBuild` **必须数组**：传 `0` 或 `"0"` 会报 `『影响版本』不能为空`；正确写法 `["trunk"]`。
2. `assignedTo` / `feedbackBy` 要**账号名**（`Louie.lu`），填中文姓名会指派失败。
3. 读接口返回时字段形态不同：`openedBuild` 是 `[{id:"trunk",title:"主干"}]`、`assignedTo` 是 `{account,realname}`。
4. 附件只能走页面表单（`files[]`）；REST `POST /api.php/v1/files` 一律被拒。
5. 改单必须用 `PUT /api.php/v1/bugs/{id}`（`PATCH` 返回 200 但不生效）；`DELETE` 只是软删除。
6. 步骤里的 `<img src="{文件id}.png">` 通过 API 写入不会渲染，截图以附件形式挂单、正文注明文件名。

### 提单过滤规则（默认只提「断言失败 + 稳定复现」）

| 判定 | 处理 | 说明 |
| --- | --- | --- |
| 断言失败（`ASSERT`） | ✅ 提单 | 错误里出现"断言/期望/实际/文本不匹配"等 |
| 环境问题（`ENV`） | ❌ 不提 | 110106/401/403/超时/连接不上/5xx |
| 用例或数据问题（`CASE`） | ❌ 不提 | 变量未定义、未查询到数据、元素查找超时、参数错误 |
| 其它（`UNKNOWN`） | ❌ 不提 | 归不了类，先人工看 |

稳定性：同一用例需在历史执行结果里失败 ≥ `--repeat` 次（默认 2，即至少两次执行都失败）才算"稳定复现"。
放宽：`--repeat 1`（当次失败就提）、`--include-env`、`--include-case`。

### 命令

```powershell
python run.py zentao --probe                          # 探测：登录/身份/产品/默认字段
python run.py zentao                                  # 最近一次执行结果 → 草稿（不提交）
python run.py zentao --from reports/results/api/x.xlsx
python run.py zentao --submit --yes                    # 核对草稿后真提交
python run.py zentao --submit --yes --delete-on-verify # 链路自检：提交→回读→删除
python run.py zentao --product 1 --module 393 --assignee Louie.lu --severity 2 --pri 2
```

产物：`reports/zentao/draft_<时间戳>.md`（人看）+ `.xlsx`（核对字段）。

### 实测结论（2026-11-13）

- 创建 → 回读 → 删除 **全链路通过**：`module=393 / severity=3 / pri=3 / type=codeerror / openedBuild=主干 / assignedTo=Louie.lu` 均正确落库。
- **附件走 REST 传不上去**：`POST /api.php/v1/files` 对 png/xlsx/txt 都返回"文件格式不在规定范围内"（服务端限制）。
  现在 UI 单的截图改走**页面表单上传**（`core/zentao_ui.py`，内部独立线程避免 Playwright 冲突）；接口单不配截图。
- **删除是软删除**：`DELETE /api.php/v1/bugs/{id}` 返回 success，缺陷从列表消失，但 `GET /bugs/{id}` 仍能查到；要彻底清掉到后台回收站处理。
- **修改要用 PUT**：`PUT /api.php/v1/bugs/{id}` 生效（`PATCH` 返回 200 但改不动），已封装成 `client.update_bug(id, title=..., severity=...)`。
- 老版本 `api.php` 会话登录也保留了兜底（`api-getsessionid.json` 的 `data` 是字符串的兼容已处理）。

### 配置项

| 键 | 公司环境取值 | 说明 |
| --- | --- | --- |
| `ZENTAO_URL` | `http://172.21.100.100:8101/zentao` | 不要带 `/api.php` |
| `ZENTAO_ACCOUNT` / `ZENTAO_PASSWORD` | `Louie.lu` / 见 .env | 建议换成专用机器人账号 |
| `ZENTAO_PRODUCT` | `1` | 所属产品 |
| `ZENTAO_MODULE` | `393` | 所属模块 |
| `ZENTAO_ASSIGNEE` | `Louie.lu` | 当前指派（账号名） |
| `ZENTAO_SEVERITY` / `ZENTAO_PRI` | `3` / `3` | 严重程度 / 优先级 |
| `ZENTAO_TYPE` | `codeerror` | 缺陷类型 |
| `ZENTAO_OPENED_BUILD` | `trunk` | 影响版本（主干） |
| `ZENTAO_KEYWORDS` | `自动化` | 关键词 |
| `ZENTAO_AUTO_SUBMIT` | `false` | 是否允许免 `--yes` 自动提交 |

### 在代码里当方法用

```python
from core.zentao import ZentaoClient

zt = ZentaoClient.from_env()
zt.whoami(); zt.products(); zt.users()
bug_id = zt.create_bug(
    title="【自动化-测试环境】xxx 失败：现象",
    steps=("<p><strong>[步骤]</strong></p><p>1. ...</p>"
           "<p><strong>[接口]</strong></p><p>POST https://.../importPayroll（HTTP 200）</p>"
           "<p><strong>[请求参数]</strong></p><pre>{...}</pre>"
           "<p><strong>[接口返回]</strong></p><pre>{\"code\":200}</pre>"
           "<p><strong>[期望]</strong></p><p>...</p><p><strong>[实际]</strong></p><p>...</p>"),
    product=1, module=393, severity=3, pri=3, bug_type="codeerror",
    assigned_to="Louie.lu", feedback_by="Louie.lu", opened_build="trunk", keywords="自动化")
zt.delete_bug(bug_id)     # 软删除（列表消失，后台可彻底删）
```

## 11. 已知问题 / 环境注意

1. **权限缓存问题**：新扫码会话调 `center:payrollSalaryPackage:list` 返回 `110106 没有访问权限`，`.env` 里的旧 token 正常 → 疑似权限缓存未刷新（建议提单）。
2. **错误 token 返回 500**：`Authorization: Bearer <乱码>` 返回 `{"code":500,"msg":"Internal Server Error"}`，正常应为 401。
3. **UI 侧存量用例的 3 类问题已修复**（本次）：
   - `pt_testcases.yaml` 的 `${candidateName}` → `{{candidateName}}`（新增 `{{变量}}` 转义语法：原样输出 `{变量}` 字面量，不会被框架替换）；
   - `new_preparation.yaml` 的 element `end_invoice_submit_2` → `after_onboarding_2`（过保回访页提交）；
   - 项目「招聘平台新建岗位-维护版」指向的 yaml 不存在 → 已临时注释停用。
   > 这三处如需回归验证，得跑对应的招聘平台全流程（会真实新建岗位/编制）。
4. **token 约 2 小时过期**，需要定期更新 `.env`（或跑一次有头 UI 用例扫码刷新）。
5. `test_test.xlsx`（调试项目）里有空行/空 sheet，lint 会告警，不影响其它项目。
6. **禅道附件 API 上传被服务端限制**（png/xlsx/txt 都被拒）：UI 单的截图改走**页面表单上传**
   （`core/zentao_ui.py`），接口单按约定不配截图。
7. **禅道 REST 删除是软删除**（列表消失、`GET /bugs/{id}` 仍可查）：验证过程产生的
   9775 / 9776 / 9777 / 9781 / 9778 / 9783 需要到后台回收站彻底清理。

---

## 12. 新增内容的约定

**新增接口用例集**：Excel 放 `api/testcase/` → 在 `api/config/setting.py` 的 `TEST_FLIELOADS` 加一行 → `python run.py lint --project <名>` → `python run.py api <名>`。

**新增接口动作**：在 `api/common/executor.py` 加一个 `elif method == 'xxx':` 分支 → lint 自动识别（无需改 lint）→ 在用例 `method` 列使用。

**新增 UI 用例集**：YAML 放 `ui/testcases/` → `tools/ui_capture.py` 采集元素并写入 `ui/config/locators/<项目>.yaml` → 在 `ui/config/settings.py` 的 `PROJECT_CONFIGS` 加一项（`PAGE_NAME` / `TESTCASES_PATH` / `ELEMENT_LOCATORS` / `LOADING_SELECTOR`）→ `python run.py lint --suite ui` → `python run.py ui <名>`。

**新增页面对象**：`ui/pages/<page_name>.py` 继承 `GsrAdminPage`（或 `ScanLoginPage` / `BasePage`），并在 `PAGE_CLASSES` 注册类名、`PAGE_URLS` 注册入口地址。

---

## 13. 变更记录

| 提交 | 内容 |
| --- | --- |
| `79ce7aa` | 合并 `api` 与 `ui_playwright` 为统一框架（core 公共层、统一 .env、统一入口、统一 reports、命名空间 `api.*` / `ui.*`） |
| `5c294ce` | 新增用例静态检查 `tools/lint_cases.py` + 自测 `tools/selftest_lint.py`（动作集合反射源码） |
| `e4da02a` | 薪资包管理按薪资包ID查询：接口方法 + `pkgquery` 动作 + UI 页面对象/定位器/用例 + UI 免扫码 token 注入 + `tools/ui_capture.py` |
| `6a2b22a` | 支持 PyCharm 子目录直接运行（sys.path 引导）；修正采集工具多级菜单导航 |
| `746143c` | 重写主 README（目录结构 / 配置全表 / 命令 / PyCharm / 用例清单 / 已知问题） |
| `40c2de2` | UI 存量 3 类问题修复（`${var}`→`{{var}}` 转义、`end_invoice_submit_2`→`after_onboarding_2`、维护版项目停用），lint 归零；新增禅道客户端 `core/zentao.py` + `tools/zentao_report.py` + `run.py zentao` |
| `f259b07` | 接入公司禅道（开源版 22.6）并按提单页重写字段：产品 1 / 模块 393 / 影响版本 `["trunk"]` / 反馈者 / 指派；创建→回读→删除闭环验证 |
| `8a9001c` | 提单过滤规则（只提"断言失败 + 稳定复现"，`--repeat` 可调）；标题只取第一处断言；新增 `update_bug`（PUT 生效） |
| `0cecaa2` | 证据驱动提单：`ui/utils/evidence.py` + `tools/evidence_bug.py`（含 `--attach-to` 补附件、附件去重）+ `core/zentao_ui.py`（页面表单上传附件）+ `tools/demo_pkg_search.py`；修复页面对象把 antd 占位行当数据行的问题 |
| `3589c1b` | 提单格式统一：API/UI 用例失败自动采证据；两者共用同一模板；新增接口证据图渲染；分类器改为强断言特征优先 |
| `4bccca7` | **接口单去掉截图**，正文改为「接口 / 请求参数 / 接口返回 / 期望 / 实际」结构（返回保留 `data` 字段）；UI 单保留页面截图 |

> 原始两个框架（`D:\lu\pycharm\api`、`D:\lu\pycharm\ui_playwright`）保持原样，可继续单独使用。
