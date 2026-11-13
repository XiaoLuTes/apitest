# autotest —— 接口 + UI 自动化统一框架

把原先两个独立框架合并成一个仓库、一套配置、一个执行入口：

| 用例集 | 目录 | 驱动方式 | 用例数据 |
| --- | --- | --- | --- |
| 接口自动化 `api` | `api/` | Excel 驱动（pytest paramtrize） | `api/testcase/*.xlsx` |
| UI 自动化 `ui` | `ui/` | YAML 驱动（Playwright） | `ui/testcases/**/*.yaml` |

两个用例集共用：`.env` 配置、日志实现（`core/logger.py`）、报告目录（`reports/`）、Allure 结果（`reports/allure-results`）、pytest 根配置与执行入口。

```
autotest/
├─ run.py                # 统一执行入口（api / ui / all）
├─ conftest.py           # pytest 根配置（路径、目录、用例集校验）
├─ pytest.ini            # 两个用例集共用的 pytest 配置
├─ .env / .env.example   # 统一配置（数据库、账号、Webhook、项目默认值）
├─ core/                 # 公共层
│   ├─ paths.py          # 统一路径（全部绝对化，任意工作目录可执行）
│   ├─ env.py            # 统一 .env 加载
│   └─ logger.py         # 统一日志工厂（API_/UI_ 前缀，输出到 reports/logs）
├─ api/                  # 接口用例集（原 api 框架）
│   ├─ common/           # 请求、断言、变量、Excel、数据库、重试、薪资包工具
│   ├─ config/setting.py
│   ├─ testcase/         # 用例 Excel
│   ├─ variable/         # 全局变量 + extract 临时变量
│   ├─ conftest.py       # 会话级夹具（结果文件、Allure、企微通知、DB 关闭）
│   └─ test_file.py      # Excel 用例入口
├─ ui/                   # UI 用例集（原 ui_playwright 框架）
│   ├─ config/           # settings.py + locators/
│   ├─ pages/            # 页面对象（base_page / gsr_admin_page / scan_login_page）
│   ├─ utils/            # 浏览器、执行器、元素定位、YAML、变量、企业微信
│   ├─ testcases/        # YAML 用例 + 附件
│   ├─ conftest.py       # browser 会话级夹具
│   └─ test_from_yaml.py # YAML 用例入口
└─ reports/              # 统一产物（不进 git）
    ├─ logs/ logs_error/ # API_log_*.log / UI_log_*.log
    ├─ results/api|ui/   # 执行结果文件（Excel 副本 / YAML 结果）
    ├─ downloads/        # 接口下载文件 + UI 浏览器下载
    ├─ screenshots/      # UI 失败截图
    ├─ auth/             # 企业微信扫码登录态（cookie 复用）
    └─ allure-results/   # allure 原始结果
```

## 1. 环境准备

```powershell
pip install -r requirements.txt
# UI 用例集首次使用还需要安装浏览器驱动
python -m playwright install chromium
```

配置：复制 `.env.example` 为 `.env`，填写数据库、账号、企业微信 Webhook、默认项目名。
优先级：系统环境变量 > `.env` > 代码默认值。

## 2. 执行用例

```powershell
python run.py --list                              # 查看所有用例集与项目名
python run.py lint                                # 用例静态检查（执行前必跑，秒级）
python run.py api 薪资包结算                        # 跑接口用例
python run.py ui 薪资结算包收款包链路                 # 跑 UI 用例
python run.py all                                 # 两个用例集各跑 .env 里的默认项目
```

常用附加参数：

```powershell
python run.py api 审批流员工标签 -k 标签              # 只跑名称匹配的用例
python run.py api 薪资包结算 --report                # 跑完生成 allure html
python run.py ui 薪资结算包收款包链路 --headless       # 无头模式（二维码推送到企微）
```

也可以直接用 pytest（需先指定用例集，否则按 `all` 处理）：

```powershell
$env:TEST_SUITE="api"; $env:API_PROJECT="薪资包结算"; python -m pytest api -k file35
```

## 3. 两个用例集的约定差异

| 项 | 接口用例集 | UI 用例集 |
| --- | --- | --- |
| 项目名变量 | `API_PROJECT`（命令行优先） | `UI_PROJECT`（命令行优先） |
| 用例文件位置 | `api/config/setting.py` 的 `TEST_FLIELOADS` | `ui/config/settings.py` 的 `PROJECT_CONFIGS` |
| 执行结果 | `reports/results/api/*.xlsx`（源用例副本 + result 列） | `reports/results/ui/*.yaml` |
| 失败证据 | Allure 附件（请求/响应/断言） | `reports/screenshots/*.png` + Allure |

新增用例集项目：
- 接口：把 Excel 放到 `api/testcase/`，在 `TEST_FLIELOADS` 里加一行 `"项目名": "testcase/xxx.xlsx"`；
- UI：把 YAML 放到 `ui/testcases/`，在 `PROJECT_CONFIGS` 里加一项（页面对象、定位器、用例路径）。

## 4. 用例静态检查（lint）

执行前先跑一遍，把「格式/引用」类错误（一跑就崩、或静默空转）挡在执行前面。不连数据库、不连业务系统、不需要 token。

```powershell
python run.py lint                       # 等价于 python tools/lint_cases.py，全查
python run.py lint --suite api           # 只查接口用例
python run.py lint --suite ui            # 只查 UI 用例
python run.py lint --project 薪资包结算    # 只查指定项目
python run.py lint --file api/testcase/x.xlsx
python run.py lint --strict              # 警告也算失败（CI 门禁）
python tools/selftest_lint.py            # lint 自身的回归自测（验证每条规则都能命中）
```

检查内容：

| 侧 | 规则 |
| --- | --- |
| 接口 | sheet 列数/必需列/重复列头；method 合法性；db_select/db_update 的 SQL 与断言写法（含“SET autocommit 写进断言列”这类坑）；editexcel 必填项；download 的 data 结构；retry 列取值；validata/jsonpath/key 格式；extract 格式；`${变量}` 是否在 all.yaml/.env/前序 extract/download var 中 |
| UI | action 合法性；element 是否存在于定位器文件（含相近名建议）；check_exists 只允许 存在/不存在；wait 必须是整数；edit_excel 的 expected 必须为 JSON；save_text/save_value 的 data 必须是变量名；YAML 占位符未加引号（被解析成 dict）；`${var}` 与 `{var}` 混用；`{变量}` 是否已定义；用例 id 重复；page 是否合法 |

合法动作集合从 `api/common/executor.py`、`api/common/request_util.py`、`ui/utils/executor.py` 反射得到，动作增删后自动跟随。
退出码：存在错误 = 1（`--strict` 时警告也算），否则 0。`--format json` 可输出机器可读结果，便于接 CI 或后续自动提单。

## 5. 详细文档

两个用例集的完整写法说明保留在各自目录下：

- 接口用例集：`api/README.md`（Excel 列定义、动作表、断言、变量、薪资包相关动作等）
- UI 用例集：`ui/README.md`（YAML 步骤、动作、元素定位、扫码登录等）

## 6. UI 登录态：token 注入免扫码（推荐）

UI 用例集的登录原本是「企业微信扫码 + cookie 复用」。现在支持直接用 .env 的 `ACCESS_TOKEN_ADMIN` 注入登录态，**免扫码**：

```powershell
python run.py ui 薪资包管理查询 --headless     # 无头也能跑，不需要扫码
```

实现：`ui/utils/browser.py` 的 `_inject_token()`，把 token 写成 `GSR-Token` cookie 再开页面。
要点（实测踩过的坑）：

- token 模式下**不再加载** `reports/auth/*.json` 旧登录态，否则请求会带上过期会话的 cookie，服务端按旧会话鉴权 → `110106 没有访问权限`。
- 新扫码建立的会话反而可能缺 `center:payrollSalaryPackage:list` 权限；.env 里的 token 权限是完整的。
- token 约 2 小时过期（`ACCESS_TOKEN_ADMIN` 从浏览器 `GSR-Token` cookie 拷），过期后会自动回落到扫码流程。
- 关闭开关：`.env` 里 `UI_LOGIN_BY_TOKEN=false`。

## 7. 示例用例集：薪资包管理查询（接口 + UI 双层）

需求：管理端 → Payroll → 算薪 → 薪资包管理，按「薪资包ID」查询。

| 层 | 项目名 | 用例文件 | 数量 | 覆盖 |
| --- | --- | --- | --- | --- |
| 接口 | `薪资包管理查询` | `api/testcase/test_payroll_package_query.xlsx` | 10（准备1+执行8+清理1） | 按ID查询命中/不存在/组合条件/结算包ID/框架方法/变量传递/未鉴权 |
| UI | `薪资包管理查询` | `ui/testcases/payroll_package/package_query.yaml` | 3 | 按ID查询命中（校验类型/月份/供应商/国家/人数/状态/分页）/不存在时暂无数据/重置恢复 |

```powershell
python run.py api 薪资包管理查询
python run.py ui 薪资包管理查询 --headless
```

框架里新增的可复用能力：

- 接口：`api/common/payroll_package.py`
  `query_salary_packages(**filters)` / `get_salary_package(code)` / `require_salary_package(code)` /
  `package_variables(row)` / `assert_row_fields(row, "字段=值,字段=值")`
- 接口用例动作：`method: pkgquery`（data `{"code":"SAL-...","filters":{}}`，validata 写 `pkg_status=0,pkg_country=Canada`），
  查询成功后把 `pkg_id/pkg_code/pkg_status/pkg_country/...` 写进变量供后续用例引用。
- UI：`ui/pages/payroll_package_page.py`（`open_package_management()` / `query_by_package_code(code)` /
  `get_row_by_code(code)` / `assert_package_row(code, 状态="待发起算薪")` / `assert_empty()`），
  定位器在 `ui/config/locators/payroll_package_management.yaml`。

## 8. 现场采集工具（找元素）

```powershell
# 按菜单路径导航并导出候选定位器 + 截图 + HTML（支持多级菜单，登录态失效时会等你扫码）
python tools/ui_capture.py --menu "Payroll/算薪/薪资包管理" --headless
# 直接打开指定 URL
python tools/ui_capture.py --url https://test-admin.gsrtech.com/center/payroll/payrollSalary/packageManagement
# 顺带验证按关键字搜索的结果
python tools/ui_capture.py --url <URL> --query SAL-20261112-0001
```

产物写到 `reports/_probe/`：输入框（含 form-item 标签）、按钮、表头、首行单元格、页面 HTML。
后续丢需求给我时，我用它现场采集元素，再写进定位器 YAML。

登录态说明：token 模式（.env 有 `ACCESS_TOKEN_ADMIN`）下采集工具同样免扫码；
没有 token 时复用 `reports/auth/*.json`，都失效则会在有头浏览器里等你扫码（`--wait` 秒）。

PyCharm 直接运行：`api/conftest.py` / `ui/conftest.py` 已带 sys.path 引导，
所以即使在 `api/`、`ui/` 子目录下右键运行也不会 import 失败；
但直接跑用的是 .env 里的默认项目（`API_PROJECT` / `UI_PROJECT`），跑指定项目请用 `run.py` 或改 .env。

## 9. 说明

- 原有独立框架（`D:\lu\pycharm\api`、`D:\lu\pycharm\ui_playwright`）保持原样，可继续单独使用；本仓库是合并后的新框架。
- 所有路径都基于 `core/paths.py` 计算成绝对路径，因此在 PyCharm 里直接运行某个测试文件、或在任意目录执行 `python D:\lu\pycharm\autotest\run.py api ...` 都能正确定位用例与报告。
