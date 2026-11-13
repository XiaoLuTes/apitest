# autotest —— 接口 + UI 自动化统一框架

一套配置、一个入口、一个报告目录，同时驱动两个用例集：

| 用例集 | 目录 | 驱动方式 | 用例数据 | 执行入口 |
| --- | --- | --- | --- | --- |
| 接口自动化 `api` | `api/` | Excel 驱动（pytest parametrize） | `api/testcase/*.xlsx` | `api/test_file.py` |
| UI 自动化 `ui` | `ui/` | YAML 驱动（Playwright） | `ui/testcases/**/*.yaml` | `ui/test_from_yaml.py` |

共用：`.env` 配置、日志（`core/logger.py`）、报告目录（`reports/`）、Allure 结果、pytest 根配置、统一入口 `run.py`。
两个用例集都用 **数据文件**（Excel / YAML）描述用例，所以新增用例通常只需要写数据文件，不用写代码。

## 目录结构

```
autotest/
├─ run.py                    统一入口：api / ui / all / lint / --list
├─ conftest.py               pytest 根配置（sys.path、报告目录、用例集校验）
├─ pytest.ini                两个用例集共用的 pytest 配置
├─ .env / .env.example       统一配置（数据库、token、企微 Webhook、默认项目）
├─ requirements.txt
├─ core/                     公共层
│   ├─ paths.py              统一路径（全部绝对化，任意工作目录可执行）
│   ├─ env.py                统一 .env 加载（系统环境变量优先）
│   └─ logger.py             日志工厂（API_/UI_ 前缀 → reports/logs）
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
│   ├─ variable/             all.yaml（全局变量）+ extract.yaml（运行期临时变量，不入库）
│   ├─ conftest.py           会话级夹具（结果文件、Allure、企微通知、DB 关闭）
│   └─ test_file.py          Excel 用例入口
├─ ui/                       UI 用例集
│   ├─ config/
│   │   ├─ settings.py       项目注册表 PROJECT_CONFIGS + 页面/URL/登录态配置
│   │   └─ locators/         元素定位器 YAML（按项目一份）
│   ├─ pages/                页面对象：base_page / gsr_admin_page / scan_login_page / payroll_package_page
│   ├─ utils/                浏览器、执行器、元素定位、YAML、变量、企业微信
│   ├─ testcases/            YAML 用例 + 附件
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

已经封成框架能力，**配置全放 `.env`，代码只写一次**：

| 文件 | 作用 |
| --- | --- |
| `core/zentao.py` | 禅道客户端（v18+ REST 优先，自动回落老版本 `api.php` 会话） |
| `tools/zentao_report.py` | 读执行结果 → 聚合失败 → 生成草稿 / 提交 |
| `run.py zentao ...` | 命令行入口 |

```powershell
python run.py zentao --probe                 # 探测：登录态、当前用户、产品/模块/用户端点是否可用
python run.py zentao                         # 取最近一次执行结果 → 生成提单草稿（不提交）
python run.py zentao --from reports/results/api/xxx.xlsx
python run.py zentao --product 3 --module 12 --assignee zhangsan --severity 2 --pri 2
python run.py zentao --submit --yes           # 真正提交（需要 .env 配置齐全）
```

行为约定：

- **默认只出草稿**：`reports/zentao/draft_<时间戳>.md` + `.xlsx`，你核对后再说提交。
- **同根因聚合**：错误文本抹掉数字/id/时间戳后做指纹，一条根因只出一条缺陷（备注里列出合并的用例）。
- **安全闸**：必须 `--yes` 或 `.env` 的 `ZENTAO_AUTO_SUBMIT=true` 才会真的调接口提单。
- **不依赖禅道也能用**：没配禅道时草稿照样生成，草稿里的标题/重现步骤可以直接手工贴进禅道。

### 需要提供的配置（`.env`）

| 键 | 说明 | 必填 |
| --- | --- | --- |
| `ZENTAO_URL` | 禅道根地址，**不要带 `/api.php`**（如 `https://zentao.example.com`） | 是 |
| `ZENTAO_ACCOUNT` / `ZENTAO_PASSWORD` | 账号密码（建议专用机器人账号，需"提Bug"权限） | 与 token 二选一 |
| `ZENTAO_TOKEN` | 已有 token 时直接填，免登录 | 与账号密码二选一 |
| `ZENTAO_PRODUCT` | 产品 id（`--probe` 会列出来） | 提单必填 |
| `ZENTAO_MODULE` | 模块 id（0 = 根模块） | 可选 |
| `ZENTAO_ASSIGNEE` | 默认指派给（禅道账号名，不是姓名） | 可选 |
| `ZENTAO_SEVERITY` / `ZENTAO_PRI` | 严重程度 / 优先级，1~4（1 最高） | 可选（默认 3） |
| `ZENTAO_TYPE` | 缺陷类型：`codeerror` / `performance` / `standard` / `automation` / `others` | 可选 |
| `ZENTAO_OPENED_BUILD` | 影响版本 id，留空用 `trunk` | 可选 |
| `ZENTAO_VERIFY_SSL` | 自签证书环境设 `false` | 可选 |
| `ZENTAO_AUTO_SUBMIT` | 是否允许免 `--yes` 自动提交（默认 `false`） | 可选 |

### 在代码里当方法用

```python
from core.zentao import ZentaoClient

zt = ZentaoClient.from_env()
zt.whoami()                      # 连通性 + 身份
zt.products()                    # → [{'id': 3, 'name': '...'}, ...]
zt.modules(3)                     # → 模块树
zt.create_bug(title="[自动化] xxx 失败", steps="重现步骤...", product=3, module=12,
              severity=2, pri=2, assigned_to="zhangsan", attachments=["reports/xxx.xlsx"])
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
| `79ce7aa` | 合并 `api` 与 `ui_playwright` 为统一框架（core 公共层、统一 .env、统一入口、统一 reports、包命名空间 `api.*` / `ui.*`） |
| `5c294ce` | 新增 `tools/lint_cases.py` + `selftest_lint.py`（用例静态检查，动作集合反射源码） |
| `e4da02a` | 薪资包管理按薪资包ID查询：接口方法 + `pkgquery` 动作 + UI 页面对象/定位器/用例 + UI 免扫码 token 注入 + `tools/ui_capture.py` |
| `6a2b22a` | 支持 PyCharm 子目录直接运行（sys.path 引导）；修正采集工具多级菜单导航 |
| `本次提交` | UI 存量 3 类问题修复（`${var}` → `{{var}}` 转义、`end_invoice_submit_2` → `after_onboarding_2`、维护版项目停用），lint 全量 **0 错误**；新增禅道提单能力：`core/zentao.py`（客户端）+ `tools/zentao_report.py`（失败聚合/草稿/提交）+ `run.py zentao` 子命令 |

> 原始两个框架（`D:\lu\pycharm\api`、`D:\lu\pycharm\ui_playwright`）保持原样，可继续单独使用。
