# 接口自动化测试框架

> 假勤 / 审批流项目的 **pytest + Excel 数据驱动** 接口自动化测试框架
> 最后更新：2026-11-13 ｜ 本文描述的是**当前代码的实际行为**，与旧版 `readme.txt` 的差异见 [第 12 节](#12-文档变更记录)

| 项目 | 说明 |
| --- | --- |
| 技术栈 | pytest + requests + openpyxl + PyYAML + PyMySQL + jsonpath + allure |
| 被测环境 | `https://test-admin.gsrtech.com`（测试 / 预生产 / 生产可切换） |
| 执行入口 | `python run.py` |
| 用例载体 | `testcase/*.xlsx`，一行一条用例，新增用例不用改代码 |
| 变量载体 | `variable/all.yaml`（全局） + `variable/extract.yaml`（运行时） |

## 目录

1. 框架简介
2. 目录结构
3. 环境准备
4. 快速开始
5. Excel 用例编写规范
6. 变量机制
7. 配置说明
8. 一次执行到底做了什么
9. 报告与日志
10. 常见问题（FAQ）
11. 安全与已知限制
12. 文档变更记录

---

## 1. 框架简介

- **数据驱动**：用例写在 Excel 里，一行一条，新增用例不需要改代码。
- **一条用例**可以是：只发 HTTP 请求（含 `upload` 文件上传）/ 只操作数据库（`db_select`、`db_update`）/ 先发请求再查库校验。
- **用例之间有顺序依赖**：登录拿 token → 发起审批拿 instanceId → 查任务拿 taskId，靠"变量"串联（⚠️ 详见 [FAQ Q2](#q2-为什么第一条用例失败后后面一大片全失败)）。
- **会话级自动化**：会话开始时重置运行时变量文件；会话结束时把执行结果**一次性**写入独立的结果文件（源用例文件只读）。

---

## 2. 目录结构

```text
api/
├── common/                      # 公共模块
│   ├── __init__.py
│   ├── allure_util.py           # 把结果文件作为附件写入 allure 报告
│   ├── database.py              # 数据库操作（连接单例、查询/更新、DB 断言）
│   ├── excel_read.py            # Excel 用例读取 + 结果缓存与写入结果文件
│   ├── executor.py              # 用例执行器（核心调度）
│   ├── logger.py                # 日志（全量 / 错误 / 控制台）
│   ├── request_util.py          # 接口请求封装
│   ├── run_state.py             # 运行时状态：变量依赖（失败→下游跳过）、通过/失败/跳过计数
│   ├── variable_handle.py       # 变量替换、变量提取、断言校验
│   ├── wecom.py                 # 企业微信群机器人通知（会话结束推送结果）
│   └── yaml_util.py             # 全局变量文件读写
│
├── config/                      # 配置
│   ├── __init__.py
│   └── setting.py               # 全局配置（环境、域名、超时、数据库、路径）
│
├── reports/                     # 报告与日志（运行后自动产生）
│   ├── logs/                    # 全量日志  API_log_YYYYMMDD.log
│   ├── logs_error/              # 错误日志  API_error_log_YYYYMMDD.log
│   ├── results/                 # 用例执行结果文件（源用例的完整副本 + result / response 列）
│   └── temp/                    # allure 原始结果（下次运行前会清空）
│
├── testcase/                    # 用例
│   ├── test_approval.xlsx       # 假勤项目用例（业务主用例集）
│   ├── test_payroll.xlsx        # payroll 项目用例（CURRENT_PROJECT=payroll 时执行）
│   ├── test_test.xlsx           # 框架调试用例（数据库增删，作为收尾清理）
│   └── test_yl.yaml             # yaml 格式用例（当前未接入执行链路，见 11.2）
│
├── variable/                    # 变量
│   ├── all.yaml                 # 测试环境全局变量
│   ├── all_prepro.yaml          # 预生产环境全局变量（当前为空）
│   ├── all_pro.yaml             # 生产环境全局变量（当前为空）
│   └── extract.yaml             # 运行时变量（自动生成 / 重置；已加入 .gitignore）
│
├── conftest.py                  # 会话级 fixture（变量文件初始化、结果落盘、关库）
├── pytest.ini                   # pytest 配置（testpaths、allure 输出目录、-vs）
├── .env.example                 # 敏感配置模板（复制成 .env 使用；.env 不入库）
├── .gitignore                   # 忽略运行产物与敏感文件
├── requirements.txt             # 依赖库
├── run.py                       # 执行入口
├── test_file.py                 # 用例驱动（参数化读取 Excel 每一行）
└── README.md                    # 本文档
```

---

## 3. 环境准备

- **Python**：3.11（当前开发环境版本）
- **安装依赖**：

```bash
pip install -r requirements.txt
```

- **配置敏感信息**：复制配置模板并按实际情况填写（`.env` 已被 `.gitignore` 忽略，不会入库）

```bash
copy .env.example .env        # Windows
cp .env.example .env          # Linux / macOS
```

| 依赖 | 版本 | 用途 |
| --- | --- | --- |
| pytest | ~=7.2.0 | 测试框架 |
| allure-pytest / allure-python-commons | ~=2.15.0 | 测试报告 |
| requests | ~=2.28.1 | 接口请求 |
| openpyxl | ~=3.1.0 | Excel 用例读写 |
| PyYAML | ~=6.0.1 | 变量文件读写 |
| jsonpath | ~=0.82 | 响应取值与断言 |
| PyMySQL | ~=1.1.2 | 数据库操作 |
| pywin32 | 最新（仅 Windows） | `editexcel` 调 WPS / Excel 的 COM 接口（见 5.7） |

- **（可选）查看 allure 报告** 需要额外安装 allure 命令行，见 [第 9 节](#9-报告与日志)。

---

## 4. 快速开始

**第 1 步：确认配置** —— 改 `config/setting.py`，或用环境变量覆盖（见 [第 7 节](#7-配置说明)）。至少确认 `ENV`（环境）和 `CURRENT_PROJECT`（跑哪个用例文件）。

**第 2 步：写用例** —— 在 `testcase/test_approval.xlsx` 新增一行，列的含义见 [第 5 节](#5-excel-用例编写规范)。

**第 3 步：执行**

```bash
python run.py
# 等价于 pytest；pytest.ini 已配置 testpaths=. 、-vs、--alluredir ./reports/temp --clean-alluredir
```

跑完看三个地方：

| 位置 | 看什么 |
| --- | --- |
| 控制台 | 用例通过 / 失败概览 |
| `reports/results/` 下的结果文件 | 每条用例的 **用例结果**（`result` 列）与 **接口返回**（`response` 列）+ 本次通过/失败/跳过条数（写在文件名里）；源用例文件不再改动 |
| `reports/logs/` | 排查失败原因 |

---

## 5. Excel 用例编写规范

表头（第 1 行）必须存在，**列名不要改**（列名会作为字典 key，`result` / `response` / `retry` 列是按表头名自动识别的）。标准结构 10 列（第 7 列 `response` 写接口返回，第 10 列 `result` 写用例结果）；如需失败重试，**在最右侧再加一列表头 `retry`**（见 [5.8](#58-失败重试retry)）：

| # | 列名 | 是否手填 | 说明 |
| --- | --- | --- | --- |
| 1 | `case_id` | 是 | 用例编号。**只用于日志和 allure 标题**，不影响结果写入位置（结果按用例真实行号写入，编号可以不连续）。建议同一 sheet 内唯一 |
| 2 | `name` | 是 | 用例名称。**以 `管理端` / `员工端` 开头决定用哪个域名**；不匹配时报 WARNING 并用 `DEFAULT_URL`（默认管理端），路径仍正常拼接。支持 `${变量}`，会作为 allure 标题 |
| 3 | `headers` | 是 | 请求头。推荐直接写变量，如 `${headers_admin}`；也可写 JSON 文本 |
| 4 | `method` | 是 | 大小写不敏感。HTTP：`get/post/put/patch/delete/head/options`；文件上传：`upload`（等价 POST）、`upload:put`、`upload:patch`；文件操作：`download`（下载落盘）、`editexcel`（调 WPS/Excel 改单元格，**仅本机**，见 5.6 / 5.7）；业务组合动作：`payrollconfirm`（读国家模板拼 map 后调确认发起结算，见 5.9）；数据库：`db_select` / `db_update`。⚠️ `head` / `options` 会忽略 `data` |
| 5 | `url` | 是 | 接口路径，可含变量，如 `/api/center/template/reject/task/${taskid}?isProxy=true`。以 `http://`、`https://` 开头则视为完整地址，不再拼域名 |
| 6 | `data` | 是 | `get` → 查询参数字符串（`pageNum=1&pageSize=10`）；`post/put/patch/delete` → JSON 文本请求体（变量可嵌在字符串里）；`upload` → 本地文件路径，或 JSON 对象（见 [5.4](#54-文件上传upload)）；`download` / `editexcel` → JSON 对象（见 [5.6](#56-文件下载download) / [5.7](#57-excel-编辑editexcel)）；`db_*` → SQL 语句 |
| 7 | `response` | **留空** | **接口返回原文**：跑完自动写入响应文本；请求没发出去（变量缺失 / 被跳过）时为空 |
| 8 | `extract` | 否 | 变量提取，JSON 文本，如 `{"taskid": "$.data.taskId"}`。表达式以 `$` 开头 → JSONPath；其它 → 正则（**推荐 JSONPath**）。取不到内容本条用例直接失败 |
| 9 | `validata` | 否 | 断言，JSON 文本。留空 → HTTP 用例跳过断言（⚠️ 数据库用例语义不同，见 5.3） |
| 10 | `result` | **留空** | **用例结果**：跑完自动写入 `通过` / `失败：原因` / `跳过：原因`；和接口返回分开，一眼就能看出用例过没过 |
| 11 | `retry` | 否 | 失败重试：留空 = 用 `HTTP_RETRY_TIMES`（默认 1 次）；数字 = 总尝试次数（含第一次）；也可写 JSON `{"times": 3, "interval": 1}`。只对 HTTP 用例生效，见 [5.8](#58-失败重试retry) |

### 5.1 断言写法（HTTP 用例）

```json
{"$.code": "200", "$.msg": "成功"}
{"$.rows[?(@.instanceId==\"${instanceid_reject}\")].status": "3"}
```

**比较规则：**

| 期望值 | 比较方式 |
| --- | --- |
| `null` | 实际必须取不到（JSONPath 未匹配，或值本身就是 `null`） |
| 数字 | 按数值比较（`200` 与 `"200"`、`12.0` 与 `"12.00"` 视为相等） |
| `true` / `false` | 按布尔比较（大小写不敏感） |
| 其它 | 按字符串比较 |

> ⚠️ 数字样字符串也会按数值比较，例如 `"007"` 与 `"7"`、`"1e3"` 与 `"1000"` 会判为相等。若需要严格字符串比较，请把期望值写成非纯数字形式（或联系维护人加开关）。
>
> 多个断言项中任意一项不通过，该用例即失败，失败信息会列出每一项的「期望值 / 实际值 / 类型 / 比较方式」。

### 5.2 数据库用例的断言（第 9 列 `validata`）

**`db_select`（查库校验）**

| 写法 | 含义 |
| --- | --- |
| 留空 / `empty` / `null` / `[]` | 期望查询结果为 **0 行**（注意：这里是"必须为空"，不是"跳过断言"） |
| `count:3` | 查询结果正好 3 行 |
| `count>:0` | 查询结果大于 0 行 |
| `contains:xxx` | 任意一行任意字段包含 `xxx` |
| `字段=值` | 存在某行该字段等于该值（支持 `字段1=值1,字段2=值2`） |
| 直接写一个值 | 查询结果只有一行一列时与该值比较（数字按数值比较） |

**`db_update`（增删改，一般用于收尾清理）**

| 写法 | 含义 |
| --- | --- |
| 留空 | 不校验（只执行 SQL） |
| `count:3` / `count>:0` / `empty` | 与"影响行数"比较 |
| 其它值 | 与"影响行数"做字符串比较 |

> 执行后日志会打印"期望 vs 实际影响行数"，便于核对。

### 5.3 示例（新增一行用例）

| 列 | 值 |
| --- | --- |
| `case_id` | 34 |
| `name` | 管理端-审批-查询待办列表 |
| `headers` | `${headers_admin}` |
| `method` | post |
| `url` | `/api/center/approval/todo?isProxy=true` |
| `data` | `{"pageNum": 1, "pageSize": 10}` |
| `result` | （留空，跑完自动写入） |
| `extract` | `{"task_id": "$.data.rows[0].taskId"}` |
| `validata` | `{"$.code": "200", "$.msg": "成功"}` |

---

### 5.4 文件上传（upload）

`method` 填 `upload`（等价 POST）、`upload:put` 或 `upload:patch`；`data` 有两种写法。

**写法一：只传一个文件**

| 列 | 值 |
| --- | --- |
| `method` | upload |
| `data` | `testcase/模板.xlsx` |

multipart 字段名固定为 `file`。

**写法二：带表单字段（JSON）**

```json
{"file": "testcase/附件/对账单.xlsx", "file_field": "settlementFile", "gsrPayrollReconciliationPackageId": "509"}
```

| 键 | 说明 |
| --- | --- |
| `file` | **必填**：本地文件路径（相对路径以项目根目录为基准，也可写绝对路径） |
| `file_field` | multipart 里的字段名，默认 `file` |
| 其它键 | 原样作为普通表单字段发送；值只支持字符串 / 数字，不支持嵌套对象或数组 |

变量正常可用，例如 `{"file": "${upload_file}", "file_field": "settlementFile", "gsrPayrollReconciliationPackageId": "${package_id}"}`。⚠️ 变量外层**建议保留引号**（写 `"${var}"`），否则变量值是字符串时会解析失败。

**注意事项**

- **不要写 `Content-Type`**：upload 分支会**强制剔除**它，由 requests 自己生成 `multipart/form-data; boundary=...`。从浏览器“复制为 cURL”抄来的 `Content-Type`（带旧 boundary）、`Content-Length`、`Host` 都是客户端自动生成的，抄进去会让服务端解析不出任何字段。
- **相对路径以项目根目录为基准**（`setting.BASE_DIR`，即 `config/` 的上一级），不依赖当前工作目录；从任意目录启动、Jenkins 用 `dir()` 切目录都能正确解析。
- 服务端收到的**只有文件名**（不含目录），即 `os.path.basename` 的结果。
- 上传的响应就是普通 HTTP 响应，`extract` / `validata` 用法与其它接口一致（响应不是合法 JSON 时断言会直接失败）。
- 框架**不会修改被上传的文件**，也不做任何文件内容处理；上传的就是磁盘上的原文件。

> 上传对账单这类“后端会校验文件内容”的接口，文件本身必须已满足校验规则，详见 [11.3](#113-其他已知限制)。

---

### 5.5 按 sheet 分层（数据准备 / 测试执行 / 数据清理）

一个用例文件里可以放多个 sheet，框架**按 sheet 在 Excel 中的顺序依次执行**，每个 sheet 内仍按行号从上到下执行。

推荐约定（**不强制，sheet 名随意**，只是便于阅读和统计）：

| sheet | 用途 | 典型内容 |
| --- | --- | --- |
| `数据准备` | 造数 | 登录、创建薪资包 / 对账包、提取 id 与 code |
| `测试执行` | 被测行为 | 真正要验证的接口 + 断言 |
| `数据清理` | 收尾 | 删除或还原数据，放在最后 |

- **执行顺序 = sheet 顺序**：`数据准备` 里 `extract` 出来的变量，`测试执行` 可以直接用 `${变量}` 引用；
- **依赖跳过跨 sheet 生效**：`数据准备` 里某条失败 → 它产出的变量被标记不可信 → `测试执行` 中**引用这些变量**的用例自动 skip（没引用的照常执行）；
- **统计按 sheet 分开**：会话结束的日志与企微卡片会输出分表统计，例如 `数据准备 通过12 失败0 跳过0 | 测试执行 通过2 失败1 跳过0`；
- **结果文件保留全部 sheet**（完整副本），可以和分表统计一一对上；
- ⚠️ 结果文件名里的 `通过N_失败N_跳过N` 仍是**全量**统计（含准备与清理步骤）；只看业务用例请看日志 / 卡片里的分表那一行；
- ⚠️ 分表统计以 **sheet 名** 为 key。同一个 Excel 内 sheet 不会重名；如果以后做多文件执行，不同文件里的同名 sheet 会合并统计。

---

### 5.6 文件下载（download）

`method` 填 `download`：框架**流式**接收响应并落盘（不会把整个文件读进内存），把保存路径写进 `response` 列和变量。

| 列 | 值 |
| --- | --- |
| `method` | download |
| `url` | `/api/center/country/template` |
| `data` | `{"params": {"countryCode": "FR"}, "var": "tpl_file"}` |

`data` 两种写法：

| 写法 | 含义 |
| --- | --- |
| 字符串 `countryCode=FR` | 直接作为查询参数 |
| JSON 对象 | `params`=查询参数（可省）、`var`=把保存路径写进哪个变量（可省）、`dir`=保存目录（可省） |

**行为**

- 保存目录：`setting.DOWNLOAD_PATH`（默认 `reports/downloads/`），相对路径按**项目根**解析，不依赖运行目录；保存后写入变量的是**绝对路径**
- 写入变量的路径**统一用正斜杠**（Windows 反斜杠会把后续 `{"file": "${变量}"}` 这类 JSON 用例解析坏，报“上传文件不存在”）
- 文件名优先取 `Content-Disposition`（支持 RFC5987 的 `filename*=UTF-8''...` 中文名），取不到用 `{case_id}_{时间戳}.{扩展名}`
- 同名文件**不覆盖**，自动加 `_1`、`_2`…
- HTTP ≥ 400 或文件内容为空 → **直接报错**，不会把错误页当成文件存下来

**注意**

- 只支持 GET
- `validata` / `extract` 在该方法里不生效（`validata` 写了会打 WARNING）；产出变量请用 `data.var`

---

### 5.7 Excel 编辑（editexcel）

`method` 填 `editexcel`：调用本机 **WPS / Excel** 打开文件 → 填单元格 → `CalculateFullRebuild()` 全量重算 → 保存。这样公式的**缓存值**是正确的（openpyxl 保存时不写缓存值，POI 不 evaluate 时会读到 `None`）。

| 列 | 值 |
| --- | --- |
| `method` | editexcel |
| `data` | `{"file": "${tpl_file}", "cells": {"CD9": 1.0}}` 或 `{"file": "${tpl_file}", "index_cells": {"1": 4500, "SE1": 1.15}}` |

| 键 | 说明 |
| --- | --- |
| `file` | 必填，待编辑的 xlsx（**原地覆盖**；相对路径按项目根解析） |
| `cells` | 与 `index_cells` 二选一，`{"单元格": 值}`；字符串按文本写、数字按数字写、`null` 清空 |
| `index_cells` | 与 `cells` 二选一，`{"指标编号": 值}`：按第 5 行的指标编号自动反查列坐标，写入第一个数据行（第 9 行），换国家模板不用改用例 |
| `sheet` | 可选，**重命名第一个 sheet**（不是选择 sheet） |

> ⚠️ **该方法仅支持本机执行，不支持 Jenkins。**
>
> 它通过 COM 调用 WPS/Excel，必须有**交互式桌面会话**。Jenkins 以 Windows 服务方式运行时处于 Session 0（无桌面），调用会失败或挂起。若必须在 CI 上跑，需要把 agent 改成“登录桌面运行”，或用计划任务 / PsExec 注入交互会话。
>
> 另外需要 `pywin32`（已写进 `requirements.txt`：`pywin32; sys_platform == "win32"`；手工安装用 `pip install pywin32`）。

**限制**

- 只能写合并单元格的**左上角**，写其它格会静默丢失
- 只支持 xlsx / xlsm
- 每次调用会启停一次 WPS/Excel 进程（约 1~3 秒）
- 文件被其它程序占用时会以只读方式打开 → 会明确报错

---

### 5.8 失败重试（retry）

`retry` 列控制一条 HTTP 用例最多尝试几次，**默认不重试**（`HTTP_RETRY_TIMES=1`）。

| 写法 | 含义 |
| --- | --- |
| 留空 | 用 `HTTP_RETRY_TIMES` / `HTTP_RETRY_INTERVAL`（默认 1 次 / 1 秒） |
| `3` | 最多尝试 3 次，间隔用默认值 |
| `{"times": 20, "interval": 2}` | 最多尝试 20 次，每次间隔 2 秒 |

**触发重试的条件**

- 断言失败（`AssertionError`）；
- `extract` 没取到内容（`ExtractValueError`）。

**不会重试的情况**

- 网络异常（连接失败、超时、DNS 解析失败等）——直接失败，重试通常会掩盖真实原因；
- 变量未定义、`db_*`、`download`、`editexcel` 用例——`retry` 列在这些分支不生效。

**行为说明**

- 总尝试次数**含第一次**：`3` = 第一次 + 2 次重试；
- 每次重试都会重新发请求、重新执行 `extract`、重新断言，以最后一次成功的结果为准；
- 重试期间失败那次提取到的变量可能已写入变量文件，最终成功的那次会覆盖它，用例不会被标记为不可信。

**报告里的表现**

- 不管尝试几次，`断言成功` / `断言失败` 都只挂**一个汇总附件**（所有断言项合并）；
- 响应附件名为 `响应参数（最后一次）`；若最后一次没拿到响应，会标成 `响应参数（第 N 次尝试，之后未拿到响应）`，不会拿旧响应冒充最后一次。

---

### 5.9 业务组合动作（payrollconfirm）

`method` 填 `payrollconfirm`：读本地已填好的**国家模板**，按第 5 行的指标编号把每个员工行解析成 `excelDistrictDataMap` 与 `countDataMap`，再调用 `/api/payrollCalculation/payrollCollect/confirmImport`。

为什么必须这样：该接口不吃本地文件，只吃前端解析出来的两个 map（`excelDistrictDataMap` 是「结算包编码 → 员工行 JSON 字符串」，`countDataMap` 是每个结算单的汇率/雇主总成本/发票金额等）。传空 map 会返回「保存失败[区域结算包确认上传失败]」，所以纯 Excel 编辑填不出这两个入参，需要这一层转换。

| 列 | 值 |
| --- | --- |
| `method` | payrollconfirm |
| `url` | 可留空，默认 `/api/payrollCalculation/payrollCollect/confirmImport` |
| `data` | `{"payrollSalaryPackageId": "${pkg_id}", "file": "${tpl_file}", "url": "${filled_url}", "settlementPackageCode": "${settle_code}"}` |

| 键 | 说明 |
| --- | --- |
| `payrollSalaryPackageId` | 必填，薪资包 ID |
| `file` | 必填，已填好数据的国家模板本地路径（缺省按项目根解析） |
| `url` | 必填（或用 `payrollResultFilesUrls`），第 5 步导入校验返回的国家模板地址 |
| `settlementPackageCode` | 可选，缺省取文件名里第一个 `_` 之前的部分（服务端下载的文件名就是「结算包编码_国家模板.xlsx」） |
| `payrollPayslipMatchList` / `bankFilesUrls` / `otherFilesUrls` | 可选，原样透传 |

**行为**

- 读表用 WPS/Excel 引擎打开并 `CalculateFullRebuild`，再读 `UsedRange`，所以公式格拿到的是**重算后的值**（openpyxl 读不到公式缓存值）——**因此仅支持本机，Jenkins（Session 0）不可用**；
- `countDataMap` 的字段映射：`SE1→settlementCurrencyAndPayrollCurrency`、`SE2→invoicingCurrencyAndSettlementCurrency`、`G1→totalEmployerCostSc`、`61~64→serviceFee/settingUpFee/otherServiceFee/chargeAdjustmentFromPastMonths`、`H→totalServiceFeeSc`、`I→currentPayableSc`、`J→currentPayableInvoiceAmount`、`K→vatIc`、`L2→adjustmentFromPreviousMonthIc`、`M→totalInvoiceAmount`；
- 组装后的请求体照常走 HTTP 分支，`extract` / `validata` / `response` 列用法与普通 post 一致；
- 第 9 行起、指标 `XX0` 为空的行视为非员工行跳过。

实测（测试环境，加拿大模板单员工）：`A=4910 → G1=4910/1.15=4269.57`、`H=100 → I=4369.57 → M=I/0.87=5022.49`，与接口确认后的结算单金额一致；结算包由 tag=2 流转到 **tag=5（待财务审核，该环境跳过了待业务审核）**，薪资包 `payroll_status=2`。

---

## 6. 变量机制

- **全局变量**：`variable/all.yaml`（按 `ENV` 选择），适合放账号、规则 ID、公共请求头等。
- **运行时变量**：`variable/extract.yaml`
  - 会话开始时**自动清空**，并把 `all.yaml` 的内容写进去；
  - 用例执行中用 `extract` 提取到的变量会追加写入；
  - 所以它是"运行产物"，**不要手工把它改成最终态来跑用例**。
- **引用格式**：`${变量名}`，支持嵌套（变量里再引用变量）：

```yaml
headers_omni: Authorization: Bearer ${access_token_omni}
```

> ⚠️ **变量取不到时，该用例会直接失败**，并提示"变量 `${xxx}` 未定义"。不会再带着 `${xxx}` 明文去发请求（旧版本会，容易产生"接口 500"这类误导性结果）。

### 变量依赖与自动跳过

一条用例 `extract` 出来的变量，会被记录成它产出的“输出”：

- 用例**失败或跳过**后，它声明的这些变量会被标记为**不可信**；
- 之后引用到这些变量的用例（名称、url、data、headers、validata 里出现 `${变量}`）**不再发请求，直接标记为 skipped**，跳过原因写在报告里，例如：
  `用例 2 跳过：依赖的前置用例失败 -> ${instanceid_reject}：用例1执行失败`；
- 结果文件里对应的 `result` 单元格会写入 `跳过：...`，失败用例写入 `失败：...`（接口返回原文在 `response` 列，两者分开）；

所以报告不会再有“1 条根因 + 20 条变量未定义”的噪声，而是“1 条根因 + N 条 skipped”，从第一条失败用例开始查即可。

> 该行为由 `config/setting.py` 的 `INVALIDATE_ON_ANY_FAILURE` 控制（可用同名环境变量覆盖）：`True`（默认）表示用例断言失败也视为“产出的数据不可信”；改成 `False` 则只有“没取到响应 / 提取失败”这类执行层面的失败才会连带跳过下游。

---

## 7. 配置说明

配置文件：`config/setting.py`（不含任何密码 / token）

**敏感配置放在项目根目录的 `.env`**（不入库，模板见 `.env.example`）：数据库账号密码、`USER_TOKEN` 等。
读取优先级：**系统环境变量（Jenkins 等） > `.env` > `config/setting.py` 默认值**；`.env` 里的 `USER_TOKEN` 会在会话开始时注入成运行期变量，用例里可直接用 `${user_token}` 引用（`all.yaml` 的 `headers_user` 就是这么用的）。

| 配置项 | 说明 |
| --- | --- |
| `ENV` | 环境：测试环境 / 预生产环境 / 生产环境。决定 `BASE_URLS`（域名）和 `ALL_YAML`（全局变量文件） |
| `CURRENT_PROJECT` | 用例项目：`假勤` / `payroll` / `调试` / `审批流或签自动通过` / `审批流或签矩阵` / `报销自动审批` / `报销审批人为空`（必须是 `TEST_FLIELOADS` 里已有的键）。决定 `TEST_FLIELOAD`（跑哪个 Excel） |
| `BASE_URLS` / `TEST_URL` | 各端域名（管理端 / 员工端） |
| `DEFAULT_URL` | 用例名没写"管理端 / 员工端"前缀时使用的默认端（默认 `管理端`） |
| `HTTP_TIMEOUT` | 接口请求默认超时秒数（默认 30），未显式传 `timeout` 时生效 |
| `HTTP_RETRY_TIMES` | `retry` 列留空时的默认总尝试次数（含第一次），默认 `1`（不重试） |
| `HTTP_RETRY_INTERVAL` | 两次尝试之间的默认间隔秒数，默认 `1` |
| `INVALIDATE_ON_ANY_FAILURE` | 用例失败时是否把下游变量判定为不可信（默认 `True`）；改 `False` 则只有“未取到响应 / 提取失败”才连带跳过下游 |
| `REPORT_PATH` | 报告目录（默认 `reports/`） |
| `RESULT_PATH` | 用例执行结果文件输出目录（默认 `reports/results/`） |
| `ALLURE_RESULT_PATH` | allure 原始结果目录（默认 `reports/temp/`，须与 pytest.ini 里的 `--alluredir` 一致） |
| `DOWNLOAD_PATH` | 下载文件保存目录（默认 `reports/downloads/`）；相对路径按项目根解析，下载后写入变量的是绝对路径 |
| `WECOM_WEBHOOK` | 企业微信群机器人 Webhook（留空则不发送通知；也可用系统环境变量注入） |
| `WECOM_MAX_CONTENT_BYTES` | 通知内容上限（字节），默认 4000（企微硬性上限 4096） |
| `WECOM_TIMEOUT` | 通知请求超时（秒），默认 10 |
| `WECOM_ENABLE` | 通知总开关（默认 `true`）；设成 `false` 时即使配了 Webhook 也不推送 |
| `DB_HOST` / `DB_USER` / `DB_PASSWORD` / `DB_PORT` / `DB_NAME` | 数据库连接信息 |
| `DB_TIMEOUT` | 数据库连接超时（默认 30 秒） |

**环境变量覆盖**（不改代码即可切换，便于 Jenkins 传参）：
`ENV`、`CURRENT_PROJECT`、`REPORT_PATH`、`RESULT_PATH`、`ALLURE_RESULT_PATH`、`DOWNLOAD_PATH`、`HTTP_TIMEOUT`、`HTTP_RETRY_TIMES`、`HTTP_RETRY_INTERVAL`、`INVALIDATE_ON_ANY_FAILURE`、`DB_HOST`、`DB_USER`、`DB_PASSWORD`、`DB_PORT`、`DB_NAME`、`DB_TIMEOUT`、`USER_TOKEN`、`WECOM_WEBHOOK`、`WECOM_MAX_CONTENT_BYTES`、`WECOM_TIMEOUT`、`WECOM_ENABLE`

```bat
:: Windows (cmd)
set CURRENT_PROJECT=调试
```

```powershell
# Windows (PowerShell)
$env:CURRENT_PROJECT="调试"
```

```bash
# Linux / macOS
export CURRENT_PROJECT=调试
```

> ⚠️ 预生产 / 生产环境的数据库信息与域名目前是空的，直接切 `ENV=生产环境` 会连接失败——这是有意为之的保护，请勿在没有确认的情况下放开。

---

## 8. 一次执行到底做了什么

1. **会话开始**（`conftest.py`）
   - 清空 `variable/extract.yaml`；
   - 把 `all.yaml` 的全局变量写入 `extract.yaml`；
   - 创建数据库单例（此时不连接，首次用到才连）。
2. **pytest 参数化**读取 `testcase/` 下的 Excel：**先按 sheet 顺序，再按行号**逐行生成用例。
3. **每条用例由 Executor 执行**
   - 变量替换（`name` / `url` / `data` / `headers` / `validata`）；
   - 按 `method` 分流：`db_select` / `db_update` 走数据库；其它拼域名 + 路径发请求（请求 URL、请求头、请求参数、响应都会记录到 allure）；
   - 有 `extract` 则提取变量写入 `extract.yaml`；
   - 有 `validata` 则断言（失败抛 `AssertionError`，用例标记失败）；
   - 把响应文本**缓存**起来（不立即写盘）。
4. **会话结束**（无论成功失败）
   - 把缓存的结果按源文件分组，**一次性写入结果文件**（`reports/results/`，源用例文件的完整副本 + `result` 列），**源用例文件不再被修改**；
   - 汇总本次执行的 通过 / 失败 / 跳过 条数，写进结果文件名，并把结果文件作为附件附加到 allure 报告；
   - 关闭数据库连接。

---

## 9. 报告与日志

### 日志

| 文件 | 内容 |
| --- | --- |
| `reports/logs/API_log_YYYYMMDD.log` | 全量日志（DEBUG 级，含变量替换过程） |
| `reports/logs_error/API_error_log_YYYYMMDD.log` | ERROR 级日志（含异常堆栈） |

- 控制台只显示 INFO 及以上；变量替换过程是 DEBUG 级，**只在日志文件里能看到**。
- 单文件超过 50MB 会切分，保留 5 个备份。
- 会话结束会打印两行汇总：`本次执行汇总：通过 X 失败 Y 跳过 Z`（全量）与 `分表统计：<sheet名> 通过X 失败Y 跳过Z | ...`（按 sheet 分开）。

### 用例结果文件

执行结果**不再写回源用例文件**，而是写入结果文件：

**`reports/results/{源用例文件名}_{时间戳}_通过{N}_失败{N}_跳过{N}.xlsx`**，例如 `reports/results/test_approval_20260915_163116_通过8_失败4_跳过21.xlsx`

- 文件内容 = **源用例文件的完整副本**（所有 sheet、所有列、样式原样保留）+ 本次执行的 `result` 列（用例结果）与 `response` 列（接口返回）；
- 源用例文件从此**只读**，跑测试不会再让它产生改动（git 里也不会再出现 xlsx 二进制 diff）；
- 同一轮执行产生的多个结果文件（如假勤主用例 + 调试用例）共用同一个时间戳；
- 输出目录可用环境变量 `RESULT_PATH` 覆盖（默认 `reports/results/`）；
- 文件名里的 **通过 / 失败 / 跳过条数**来自本次会话的实际执行结果，一眼就能区分批次（同一轮执行的多个结果文件时间戳相同）；**这是全量统计（含数据准备 / 清理步骤）**，只看业务用例请看日志或卡片里的「分表统计」；
- 结果文件与源文件体积相当，跑多了记得定期清理。
- **结果文件会自动作为附件挂进 allure 报告**，详见下一节。

### 企业微信通知

在 `.env`（或系统环境变量）里配置 `WECOM_WEBHOOK` 后，**会话结束会自动把执行结果推到企业微信群**：

```text
## 接口自动化执行结果
> 项目：假勤
> 结果：通过 8 失败 5 跳过 20
> 分表：数据准备 通过5 失败0 跳过0 | 测试执行 通过3 失败5 跳过20
> 失败用例：5-年假（按duration算endtime）、8-病假（按duration算endtime）
> 结果文件：test_approval_20260915_163116_通过8_失败5_跳过20.xlsx
> [查看 Allure 报告](http://jenkins/job/apitest/128/allure/)
```

- Webhook 获取：企业微信群 → 右上角「…」→ 群机器人 → 添加机器人 → 复制 Webhook 地址（形如 `https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxxx`）；
- **留空则不发送**（本地执行完全无感，只在日志里打一行 INFO）；
- **总开关**：`WECOM_ENABLE=false` 时即使配了 Webhook 也不推送（适合本地调试不想打扰群、或临时关掉某个 job）；
- Jenkins 上执行时会自动带上 `[查看 Allure 报告]` 链接（取 `BUILD_URL` 环境变量）；
- 卡片里的 `分表` 行按 sheet 名统计（如「数据准备 通过12 失败0 跳过0 | 测试执行 通过2 失败1 跳过0」）；没有分表数据时不显示这一行；
- 失败用例最多列前 10 条；内容超过 4096 字节（UTF-8）会自动截断；
- 发送失败只记 WARNING，**不影响用例结果**；机器人限 **20 条/分钟**，所以只在会话结束聚合发送一条。

### allure 报告

pytest 只生成"原始结果"到 `reports/temp`（每次运行前会清空）。要生成可浏览的 HTML 报告，需要 allure 命令行（可选安装）：

```bash
allure serve ./reports/temp                                            # 起本地服务直接看
allure generate ./reports/temp -o ./reports/allure-reports --clean     # 生成静态站点
```

> 说明：`run.py` 里的 `allure generate` 代码目前是**注释状态**，所以 `reports/` 下不会自动出现 `index.html`。

**每条 HTTP 用例的附件：**

- `请求路径` / `请求头` / `请求参数`：只挂一份；
- `断言成功` 或 `断言失败`：所有断言项合并成一个汇总，重试多次也只挂最后一次的结果；
- `响应参数`：最后一次尝试的响应；重试后最后一次没拿到响应（如网络异常）会标为 `响应参数（第 N 次尝试，之后未拿到响应）`。

**用例结果文件会一并进报告：**

- 会话结束时，除了生成结果文件，还会向 `reports/temp` 写入一条汇总记录（`*-result.json` + xlsx 附件），报告左侧会出现一个独立 suite **「用例执行结果」**，点开即可**直接下载 xlsx**；
- 报告首页的 **Environment 面板**同时登记 `env`、`project`、结果文件名和结果文件目录；
- 这条汇总记录会被 allure 计入统计（每个结果文件 +1 条），它不属于真实用例；`--clean-alluredir` 会在下次运行前把它和旧附件一起清空，不会越积越多；
- 如果用的是自定义 `--alluredir`，请同步设置环境变量 `ALLURE_RESULT_PATH`，否则附件会写到默认的 `reports/temp` 里。

---

## 10. 常见问题（FAQ）

### Q1 跑之前要注意什么？

- 源用例文件是**只读**的（结果写到结果文件里），**不需要再先关掉 Excel**。
- 但**运行期间不要编辑源用例文件的行**（插入 / 删除 / 排序）：结果行号是读取用例时确定的，中途改行会让结果落到错误的行上。
- 结果写回发生在**会话结束时**。中途 Ctrl+C 或进程崩溃，这一轮不会生成结果文件。

### Q2 前置用例失败后，后面的用例会怎样？

用例之间有**顺序依赖**：登录用例提取 token、审批用例提取 instanceId、任务用例提取 taskId，后面的用例都靠这些变量。

- 前置用例失败 → 它产出的变量被标记为不可信 → 引用到这些变量的用例**直接标记为 skipped**（不再发请求），报告里会写明跳过原因；
- 所以现在看到的是“少量失败 + 一批 skipped”，排查建议：**只看失败的那几条**，skipped 的用例不用管；
- 如果某条用例报"变量 `${xxx}` 未定义"却没有被跳过，说明**没有任何用例声明产出过这个变量**（多半是变量名写错），属于用例文件问题。

### Q3 接口报超时 / 我有个接口就是很慢怎么办？

默认超时 30 秒（`setting.HTTP_TIMEOUT`）。可以改 `setting.py` 里的 `"30"`，或临时用环境变量 `HTTP_TIMEOUT=60` 覆盖。

### Q4 只想跑某一条用例怎么弄？

由于用例有顺序依赖，单独跑某条通常没有意义。调试单条接口时建议：把该用例贴到 `testcase/test_test.xlsx`，然后 `set CURRENT_PROJECT=调试` 再执行。

### Q5 为什么我的断言"看起来该失败却通过了"？

断言做了数值比较：`200` 与 `"200"`、`"12.00"` 与 `"12.0"`、`"007"` 与 `"7"` 都判为相等。Excel 里的期望值都是字符串，注意不要依赖前导 0 / 小数位数的差异。

### Q6 为什么数据库用例明明没写断言也失败了？

`db_select` 用例的 `validata` 留空表示"期望查询结果为 **0 行**"。如果只是想执行查询不校验，请用 `count>:0` 之类表达真实期望。另外 db 用例的 `data` 列（SQL）不能为空。

### Q7 新增一列会影响执行吗？

不会。列名作为字典 key 使用，多余列会被忽略；只要第 1 行表头存在即可。但 `result` / `response` 列是按表头名识别的，把表头改名后对应的内容就不会写入结果文件（启动时会打 WARNING）。

### Q8 Excel 里空行会报错吗？

不会。所有单元格都为空的行会被自动跳过。

### Q9 怎么临时切环境？

`set ENV=预生产环境` 再执行；注意预生产 / 生产的域名与数据库配置目前为空。

### Q10 变量文件被改乱了怎么办？

`extract.yaml` 每次会话开始都会被重置，不用担心；`all.yaml` 请勿手工写运行时的 token。

---

## 11. 安全与已知限制

### 11.1 安全（建议尽快处理）

- ✅ **已处理（本轮重构）**：数据库账号密码已从 `config/setting.py` 移到项目根目录的 `.env`（`.gitignore` 已忽略 `.env`）；`variable/all.yaml` 里 `headers_user` 的字面 token 改成 `${user_token}`（值从 `.env` 注入）；`testcase/test_yl.yaml` 里的 Basic token 已移除。优先级为 **系统环境变量 > `.env` > `setting.py` 默认值**，所以 Jenkins 上直接传环境变量即可，不需要落地 `.env` 文件。
- ⚠️ **仍需手工做一件事**：
  1. **轮换凭据**（未做）：密码 / token 仍然存在于 **git 历史**里，改文件不等于删除历史，建议在服务端改一次密码 / 让旧 token 失效；代码侧只需更新 `.env`。
  2. **把运行时文件移出版本控制**（✅ 已完成）：`variable/extract.yaml`（含运行时 token）与 `.idea/` 已用下面的命令移出，本地文件保留：

```bash
git rm --cached variable/extract.yaml
git rm -r --cached .idea
```

（`git rm --cached` 只从版本控制移除，本地文件保留；`extract.yaml` 每次会话开始会自动重建，不影响执行）
- allure 报告里会记录**完整请求头（含 Authorization）**，注意报告文件的流转范围。

### 11.2 未接入的功能

- `testcase/test_yl.yaml` 以及 `yaml_util.py` 里被注释掉的 yaml 用例函数，**没有接入执行链路**，实际执行的都是 Excel 用例。

### 11.3 其他已知限制

- 用例强依赖执行顺序与真实业务数据（账号 / 规则 ID / 日期等硬编码在用例里），换环境或换数据需要同步调整；前置失败时下游会自动 skip，但**被 skip 的用例本轮等于没有验证**，修好根因后必须重跑全量。
- 结果文件是源用例文件的完整副本，每轮执行都会新增文件，需要定期清理 `reports/results/`。
- `extract.yaml` 是单文件全局状态，**不支持并发执行**（多进程会互相覆盖）。
- **带公式的 xlsx 不能用 openpyxl 改写**：这类文件（尤其是后端生成、还要传回后端的报表）经 openpyxl 读写后会**丢失公式的缓存值**（实测：某对账单 744 个缓存值掉到 64 个；`data_only=True` 会把 88 个公式直接清零），文件会被后端校验拒绝。若确需改动（例如只改 sheet 名），应改用 zip + 只替换 `xl/workbook.xml` 与 `docProps/app.xml` 文本的方案，其余部件字节保持不变。
- **对账单上传目前需人工介入**：后端要求上传文件的 sheet 名等于结算包 code，而该 code 是每次运行动态产生的，写死的文件无法匹配。当前做法是手工用 WPS / Excel 改 sheet 名（会正常重算并保存缓存值）后再上传，该用例不适合放进自动用例表。
- `__pycache__/`、`.pytest_cache/`、`reports/`、`*.log`、`.env`、`variable/extract.yaml`、`~$*.xlsx` 已由 `.gitignore` 忽略。
- **`editexcel` 仅支持本机，不支持 Jenkins**：它依赖 WPS/Excel 的 COM 接口与交互式桌面会话；Jenkins 以服务方式运行（Session 0）时无法调用，详见 [5.7](#57-excel-编辑editexcel)。

---

## 12. 文档变更记录

相对旧版 `readme.txt` 修正的内容：

1. **目录树文件名 / 目录名错误已修正**：`excel_read.yaml` → `excel_read.py`、`yaml_utils.py` → `yaml_util.py`、`test_fire.py` → `test_file.py`、`testcases/` → `testcase/`，并补上实际存在的 `variable/`、`reports/` 结构。
2. **删除过时约束**："excel 文件 code_id 不能为空且必须从 1 开始"——`case_id` 现在只作为标识，结果按用例真实行号写入，编号可以不连续。
3. **删除"需要修改路径的文件"一节**：路径现在集中在 `config/setting.py`（仅 `pytest.ini` 的 alluredir 与 `yaml_util` 的变量文件路径例外），不需要再逐文件改路径。
4. **修正报告说明**：当前不生成 `reports/index.html`，allure 原始结果在 `reports/temp`，需用 allure 命令行查看（见第 9 节）。
5. **补充了旧文档未提及的当前行为**：
   - 变量取不到 / extract 提取不到 → 用例直接失败；
   - 断言的比较规则（数值、布尔、null、字符串）；
   - 数据库断言语法（`count:` / `count>:` / `contains:` / `字段=值`）；
   - HTTP 空断言 = 跳过，`db_select` 空断言 = 期望 0 行 的语义差异；
   - 结果写入时机与输出位置（会话结束时写入 `reports/results/`，源用例文件不再被修改）；
   - 超时配置 `HTTP_TIMEOUT`；
   - 变量依赖与自动跳过（含 `INVALIDATE_ON_ANY_FAILURE` 开关）；
   - 端前缀（管理端 / 员工端）的选择规则与默认端 `DEFAULT_URL`。
6. **补充文件上传（`upload`）的用法**：`method` 新增 `upload:put` / `upload:patch`；`data` 支持“只传文件”与“带表单字段（JSON）”两种写法；补充 `Content-Type` 会被强制剔除、相对路径以项目根目录（`setting.BASE_DIR`）为基准等注意事项（见 [5.4](#54-文件上传upload)）。
7. **更新安全与已知限制**：运行时文件已移出版本控制、`.gitignore` 已生效（含 `reports/`、`.env`、`variable/extract.yaml`），凭据轮换仍待处理；新增“带公式 xlsx 不能用 openpyxl 改写”与“对账单上传需人工介入”两条（见 [第 11 节](#11-安全与已知限制)）。
8. **补充按 sheet 分层与分表统计**：一个文件可按「数据准备 / 测试执行 / 数据清理」分 sheet，框架按 sheet 顺序执行、跨 sheet 的变量与依赖跳过照常生效；会话结束的日志与企微卡片输出分表统计（如「数据准备 通过12 失败0 跳过0 | 测试执行 通过2 失败1」），结果文件名仍为全量统计（见第 5.5 节）。
9. **补充文件操作能力**：新增 `download`（流式下载落盘、路径写入变量）与 `editexcel`（WPS/Excel 重算后保存单元格）；说明 `editexcel` **仅支持本机、不支持 Jenkins**（见 [5.6](#56-文件下载download) / [5.7](#57-excel-编辑editexcel)）。
10. **补充失败重试与相关配置**：新增 `retry` 列（总尝试次数、含第一次），只重试断言失败与 `extract` 未取到内容，网络异常不重试；补充 `DOWNLOAD_PATH`、`HTTP_RETRY_TIMES`、`HTTP_RETRY_INTERVAL` 三个配置；`requirements.txt` 补 `pywin32; sys_platform == "win32"`（`editexcel` 依赖）；同步说明重试时的 Allure 附件行为（见 [5.8](#58-失败重试retry)）。

11. **新增业务组合动作 `payrollconfirm` 与 `editexcel` 的 `index_cells`**：前者读本地国家模板（WPS/Excel 重算后取值）拼出 `confirmImport` 需要的 `excelDistrictDataMap` / `countDataMap` 再提交（见 5.9）；后者支持按第 5 行指标编号填数，换国家模板不用改单元格坐标（见 5.7）；`download` 写入变量的路径统一改为正斜杠，避免 Windows 反斜杠把 `{"file": "${变量}"}` 这类 JSON 用例解析坏（见 5.6）。
