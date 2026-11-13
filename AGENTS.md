# AGENTS.md —— 自动化测试执行手册（每个 AI 对话开工前先读）

> 本文件是**唯一入口**：读完它就能从「拿到需求」一路做到「执行完 + 禅道提单」。
> 细节文档在 `README.md`；提单硬约束在 `PROMPT_bug_filing.md`（提单前必须再读一遍）。
> 本文件约定 > 临时想法。与代码冲突时，以代码现状为准，并顺手更新本文件。

---

## 0. 一句话现状

- 框架：`D:\lu\pycharm\autotest`（接口 `api/` + UI `ui/` + 公共层 `core/`，统一入口 `run.py`）
- 原始两个框架 `D:\lu\pycharm\api`、`D:\lu\pycharm\ui_playwright` **保持原样，禁止改动**（只读参考）
- 资料入口：`docs/项目资料/`（按项目分层，用户持续补充）——
  `公共/测试数据.md`（环境账号、客户/供应商/员工、DB 常用表）、`<项目>/测试数据/README.md`（该项目单据号与造数口径）、`<项目>/接口文档|数据库表结构|需求文档/`
- 测试环境：业务平台 `https://test-admin.gsrtech.com`；禅道 `http://172.21.100.100:8101/zentao`
- 执行方式：`python run.py <子命令>`（在 `D:\lu\pycharm\autotest` 下执行）

## 1. 开工前 30 秒检查

开工先读三处：`docs/项目资料/公共/测试数据.md`（环境与账号）、`docs/项目资料/<项目>/README.md` + `测试数据/README.md`（接口清单与可用单据号）、`docs/requirements/` 里同需求的历史拆分（有就接着用）。

```powershell
cd D:\lu\pycharm\autotest
python run.py --list        # 看现有用例集与项目名
python run.py lint          # 现有用例是否干净（应 0 错误）
python run.py zentao --probe # 禅道是否通（提单前才需要）
```

要点：
- `.env` 是唯一配置入口（含 `ACCESS_TOKEN_ADMIN`、`ZENTAO_*`、`DB_*`）；**不要写进 git**。
- `ACCESS_TOKEN_ADMIN` 约 2 小时过期。接口报 401/110106、UI 跳登录页 = token 过期，**先让用户更新 `.env`**，别去猜代码问题。
- 单条命令超 120 秒时用后台跑（`Start-Process ... -RedirectStandardOutput reports\run_out.txt`）再轮询，别让命令超时。
- **先确认 `ENV`**：只有 `测试环境` 允许连数据库（见第 5 节）；不是测试环境就先停下来问用户。

---

## 2. 端到端流程（六段，每段都有产物与人工闸口）

### 阶段 1 —— 需求拆分（输入：PRD/文档/截图/禅道需求号）

要做的事：
1. 提取**业务规则**、状态流转、权限差异、边界与异常、数据依赖。
2. 判断改动影响面：涉及哪些页面、哪些接口、哪些历史用例需要回归。
3. **产出 `docs/requirements/<需求名>.md`，直接套模板**：`docs/需求拆分模板.md`
   （示例：`docs/requirements/示例-薪资包管理查询.md`）。必须写全这 10 节：
   需求信息 / 需求摘要 / **规则矩阵（R1、R2…）** / **测试点清单（TP-01…→ 覆盖哪条规则 → 接口·UI·不可自动化）** /
   用例映射（评审后回填）/ **不做的场景 + 原因** / 影响面与回归范围 / 数据与前置 / 待确认与风险 / 交付清单
   硬要求：每条测试点必须挂到某条规则上（不允许无来源的测试点）；不做的场景必须写原因。
4. 需求不清晰时：**照样列测试点并在文档里标注"待确认"**，不要停下来等；公司口径是"多提、可去重、允许噪音"。
   前端造不出来的非法数据/脏数据**不做**接口健壮性用例（只验证前端有拦截即可）。

🚦 人工闸口：把「测试点清单」给用户过一眼（10 分钟）。用户说"可以"再进阶段 2。

### 阶段 2 —— 用例设计（接口 + UI 双轨）

**先复制模板，不要从空白文件开始**（模板本身是 lint 干净的，可直接当格式基准）：

| 模板 | 用途 |
| --- | --- |
| `api/testcase/test_TEMPLATE_api.xlsx` | 接口用例：三 sheet、12 列、常用动作示例（GET/POST/db_select/download/retry/负向/清理） |
| `ui/testcases/_TEMPLATE_ui_case.yaml` | UI 用例：结构 + **全部动作清单与 data/expected 语义**（写 UI 用例前必看） |
| `ui/config/locators/_TEMPLATE_locators.yaml` | 定位器：`by: id/xpath/css/name` 四种写法 + antd 按钮空格坑 |
| `docs/用例编写模板.md` | 列定义、专用动作表、命名规范、设计口径（本文档的展开版） |

先按层拆分：
- 纯后端逻辑、参数校验、数据落库、状态字段 → **接口层**
- 页面展示、交互流程、元素状态、前端校验提示 → **UI 层**
- 同一规则两层都值得验时，两层都写（接口验数据、UI 验呈现）

接口层（Excel 驱动）——**写之前先读 `docs/项目资料/<项目>/接口文档/`；没有文档就以实测抓包为准，并回填该目录**：
- 文件放 `api/testcase/test_<主题>.xlsx`，三个 sheet：`数据准备` / `测试执行` / `数据清理`
- 列：`case_id, 场景, 场景说明, name, headers, method, url, data, response, extract, validata, result`（建议再加 `备注`、`retry`）
- **`场景` + `场景说明` 必填且要写实**：场景 = `模块｜子场景` 分组名；场景说明 = `前置 + 操作 + 预期`，把具体单据号/字段值写进去（评审与提单都引用这两列，lint 会对缺失给出告警）
- `name` 以「管理端｜/员工端｜」开头（决定请求打哪个 host）
- 断言 `validata` 写 JSON：`{"$.code": 200, "$.data.id": "..."}`；DB 断言用 `db_select` + `字段=值`
- **涉及写库（`db_update` / delete / insert）必须在写用例前按第 5 节向用户确认**，未经确认不许写进用例
- 详细动作与写法：`README.md` 第 8 节 + `api/README.md`
- 注册项目：`api/config/setting.py` 的 `TEST_FLIELOADS` 加一行

UI 层（YAML 驱动）——页面结构与文案参考 `docs/项目资料/<项目>/需求文档/` 里的原型截图：
- 文件放 `ui/testcases/<项目>/<名>.yaml`；步骤字段：`step_name / element / action / data / expected`
- 元素名必须**已存在**于 `ui/config/locators/<项目>.yaml`；没有就现场采集（见阶段 2.5）
- 注册项目：`ui/config/settings.py` 的 `PROJECT_CONFIGS`（`PAGE_NAME` / `TESTCASES_PATH` / `ELEMENT_LOCATORS` / `LOADING_SELECTOR`）
- 需要新增页面对象时：`ui/pages/<page>.py` 继承 `GsrAdminPage`，并在 `PAGE_CLASSES`、`PAGE_URLS` 注册

#### 2.1 用例设计口径（写之前先对齐这 7 条）

1. **只测前端造得出来的场景**：非法枚举、空必填、跨租户 ID 这类"接口脏数据健壮性"**不做**（公司口径：前端能拦即可）。
2. **造数路径必须页面可达**：需要"包含全部标签"就用跨组标签组合，别造页面点不出来的配置。
3. **断言要验关键业务字段**：`code=200` 只证明没报错；金额、状态、数量、落库结果才是断言重点。
4. **三 sheet + 清理**：造数必须清理，跑完自检无残留（如薪资包 `status=5`、绑定结算包 `del_flag=2`）。
5. **数据唯一化**：日期/名称带唯一后缀，否则重跑会撞历史数据（如销假后同一时段不可重提）。
6. **`retry` 只用于异步状态流转**（只认纯数字或 dict），不要用它掩盖真实失败。
7. **明确列出「不做」的用例**并写原因（例：未配置国家模板的场景不做）。

### 阶段 2.5 —— 找元素（只做一次，之后复用）

```powershell
python tools/ui_capture.py --menu "Payroll/算薪/薪资包管理" --headless     # 按菜单导航
python tools/ui_capture.py --url <页面URL> --query <关键字>                 # 直接开页面 + 顺带验证搜索
```
产物在 `reports/_probe/`：`candidates_*.json`（输入框/按钮/表头/首行单元格）、`page_*.html`、`page_*.png`。
**采集工具不会自动改定位器 YAML**：人工确认后写进 `ui/config/locators/*.yaml`（`by: id/xpath/css/name` + `value`）。
antd 按钮两个汉字会插空格（`搜 索`/`重 置`），用 `xpath=//button[contains(normalize-space(.),'搜')]`。
取表格数据要排除占位行：`ant-table-placeholder` / `ant-table-measure-row`（`PayrollPackagePage` 已有实现可抄）。

### 阶段 3 —— 用例自检（机器闸口，必须过）

```powershell
python run.py lint                     # 全量
python run.py lint --project <项目名>   # 单项目
python run.py lint --suite ui --project <UI项目名> --file <某个yaml>   # 单文件（按该项目定位器校验）
```
- **有错误（退出码 1）不许执行**：打回阶段 2 改用例，不要"先跑跑看"。
- 警告可以带着跑，但要读一眼（多为 case_id 重复、占位行、sheet 名不规范）。

### 阶段 4 —— 执行

```powershell
python run.py api <项目名> [--report]
python run.py ui  <项目名> --headless
```
- 失败会自动落证据：`reports/evidence/*.json`（接口：方法/URL/请求参数/响应/断言明细；UI：步骤/接口/截图）
- 结果文件：`reports/results/api/*.xlsx`、`reports/results/ui/*.yaml`；日志 `reports/logs/`；截图 `reports/screenshots/`
- UI 侧免扫码登录靠 `.env` 的 `ACCESS_TOKEN_ADMIN`（`ui/utils/browser.py::_inject_token`）；不要为了跑 UI 去改登录逻辑
- 涉及写数据的用例，跑完确认清理 sheet 生效（别留脏数据）

### 阶段 5 —— 结果分析（我能自己做的部分）

对每条失败，判定三类之一并给出证据：
- **产品缺陷**：断言失败且可复现（接口返回与需求不符、UI 呈现与预期不符）
- **用例/数据问题**：变量未定义、前置数据不存在、元素定位写错、自身用例逻辑错
- **环境问题**：110106/401/超时/5xx/网络

判定依据优先级：证据 JSON > 接口返回原文 > 日志 > 截图。
不确定时**重跑一次**该用例集（稳定性证据），不要凭一次失败下结论。
同时报出「历史失败次数」（`tools/zentao_report.py::history_failure_counts`）。

### 阶段 6 —— 禅道提单（**必须**遵守 `PROMPT_bug_filing.md`）

```powershell
python run.py zentao                    # 生成草稿（默认不提）
python run.py zentao --submit --yes      # 人工确认后再执行
```
- 只提「断言失败 + 稳定复现（历史失败 ≥2）」；环境/用例问题只列进"按规则不提"清单交给人工
- 单据必须含：前置条件 / 步骤 / 接口 / 请求参数 / 接口返回 / 期望（人话）/ 实际 / 备注
- **接口单不带截图；UI 单必须带截图**（页面表单上传，REST 传不了附件）
- 字段：产品 1、模块 393、`openedBuild=["trunk"]`、指派/反馈者用账号名、关键词 `自动化`
- 提交后回报：单号 + 链接 + 字段回读；验证产生的测试单记得软删除并提醒用户清理回收站

🚦 人工闸口：草稿必须用户确认后才能 `--submit`。**任何情况下不得自动提交。**

---

## 3. 用例格式约束（硬性，写用例前必看）

模板：`api/testcase/test_TEMPLATE_api.xlsx`、`ui/testcases/_TEMPLATE_ui_case.yaml`、
`ui/config/locators/_TEMPLATE_locators.yaml`；展开说明见 `docs/用例编写模板.md`。
**新用例必须照模板写；存量文件缺列不算阻塞，但不许再新增缺列文件。**

### 3.1 接口用例（xlsx）

列（顺序固定，缺列 lint 会告警）：

| 列 | 必填 | 约束 |
| --- | --- | --- |
| `case_id` | ✅ | 唯一；准备/执行/清理各自前缀便于追溯 |
| `场景` | ✅ | `模块｜子场景` 分组名，同组用例共用同一个值（如 `薪资包管理｜按ID查询`） |
| `场景说明` | ✅ | 一句话写 **前置 + 操作 + 预期**，带具体单据号/字段值（如 `前置：已有 SAL-20261112-0001；操作：按ID精确查询；预期：total=1 且国家/状态与页面一致`） |
| `name` | ✅ | **必须以「管理端｜」或「员工端｜」开头**（决定 host 与鉴权头），写具体校验点 |
| `headers` | ✅ | `${headers_admin}` / `${headers_user}` 或完整 JSON |
| `method` | ✅ | `GET/POST/PUT/DELETE/PATCH` + 专用动作 `db_select/db_update/download/editexcel/upload/payrollconfirm/pkgquery` |
| `url` | ✅ | 相对路径，host 由 `name` 的端前缀决定；`db_*`/`editexcel`/`pkgquery` 可留空 |
| `data` | ✅ | 普通接口 = 参数 JSON；`db_*` = **SQL**；`download` = `{"dir","var"}`；`editexcel` = `{"file","cells"或"index_cells"}` |
| `validata` | ✅ | 普通接口 = JSON `{"$.code":200,"$.rows[0].id":"${demo_id}"}`；`db_select` = `字段=值`；`db_update` = 影响行数（写库前需用户确认，见第 5 节）；`pkgquery` = `字段=值` |
| `response` | 建议 | 框架回写返回原文，排障用 |
| `extract` | 按需 | `{"变量名":"$.path"}`，产出给后续用例 `${变量名}` |
| `retry` | 按需 | **只认纯数字或 dict**（如 `5`）；用于异步状态流转，不许用来掩盖真实失败 |
| `备注` | 建议 | 这条用例为什么存在、数据从哪来 |

其他硬性约束：

1. **三 sheet 顺序固定**：`数据准备` → `测试执行` → `数据清理`；造了数据必须清理，跑完无残留。
2. **断言不许只写 `code=200`**：必须覆盖业务字段（金额/状态/数量/落库结果）。
3. **只测前端造得出来的场景**：脏数据、非法枚举、跨租户 ID 一律不写。
4. **数据唯一化**：名称/日期带唯一后缀，否则重跑撞历史数据。
5. **变量**：`extract` / `download.var` / `pkgquery` 产出的变量可跨用例用 `${变量}`；未定义变量 lint 直接报错。
6. 单文件校验：`python run.py lint --project <项目名>`；**ERROR 不为 0 不许执行**。

### 3.2 UI 用例（yaml）

```yaml
test_cases:                     # 固定根节点
- id: 项目-01-场景               # 唯一
  name: 项目-场景-校验点          # 会进报告/证据/提单
  page: payroll_package_page     # 必须是本项目 PAGE_NAME 里的页面对象
  steps:
    - step_name: 1、做什么        # 步骤名要写清动作，会进提单的 [步骤]
      element: pkg_code_input    # 必须在 ui/config/locators/<项目>.yaml 里存在
      action: input              # 动作白名单，见模板底部清单（22 个）
      data: 'SAL-20261112-0001'  # 按动作语义：输入值/期望值/变量名/秒数/文件名
      expected: ...              # 仅 edit_excel 等用作配置 JSON
```

硬性约束：

1. `element` 必须已存在：没有就 `tools/ui_capture.py` 采集后写进定位器，**不许写"猜"的选择器**。
2. `action` 必须在白名单内；`data`/`expected` 的语义按模板注释写（如 `check_exists` 只填 `存在`/`不存在`，`wait` 填整数秒）。
3. **变量语法**：`{变量名}`（preload + 前序 `save_text/save_value`）；要字面量大括号写 `{{变量名}}`；
   `${变量名}` 是接口侧写法，**UI 里无效**。
4. 校验类断言要断言**关键业务字段**（编号/状态/金额/条数），不要只判"元素存在"。
5. 步骤要可复现：先 `wait_exists` 等元素/接口回来，再 `check_text`，不要靠固定 sleep。
6. 表格取数要排除 antd 占位行（`ant-table-placeholder` / `ant-table-measure-row`），页面对象里已有实现可抄。
7. 单文件校验：`python run.py lint --suite ui --project <项目名> --file <yaml>`。

### 3.3 命名规范

| 对象 | 规范 | 例 |
| --- | --- | --- |
| 接口 `name` | `端｜模块｜场景-预期` | `管理端｜薪资包管理｜按薪资包ID查询-命中` |
| UI `id` | `项目-序号-场景` | `薪资包管理-02-查询不存在的薪资包ID` |
| UI `name` | `项目-场景-校验点` | `薪资包管理-查询不存在的薪资包ID-列表为空` |
| 步骤名 | `序号、动作对象 + 动作` | `3、点击「搜 索」` |

## 4. 硬约束（违反即返工）

1. **只改 `autotest/`**：`D:\lu\pycharm\api`、`D:\lu\pycharm\ui_playwright` 一律只读。
2. **凭据只在 `.env`**：不写进代码、不写进文档、不提交 git；不把账号密码贴进单据。
3. **提单格式只在 `tools/evidence_bug.py::build_steps_html()` 定义**：不要在别处拼 HTML。
4. **用例数据文件**才是一等公民：新增用例优先写 xlsx/yaml，不要为一次性场景写脚本。
5. **先 lint 再执行**；**先草稿再提交**；**先重跑再判定偶发**。
6. 报告目录（`reports/`）不进 git；`api/variable/extract.yaml` 是运行期产物，也不入库。
7. 遇到不确定的环境/权限现象：**报告用户**（附错误码与证据），不要改断言去"迁就"环境。
8. **资料归档**：用户给的接口文档/表结构/PRD 一律放 `docs/项目资料/<项目>/<类别>/`，文件名 `YYYYMMDD-来源-主题.扩展名`，并在该项目 `README.md` 的「已收录清单」补一行；新增**项目数据/单据号**登记到 `<项目>/测试数据/README.md`，新增**公共数据**（账号、客户、供应商、DB 表）登记到 `公共/测试数据.md`；失效的标 `❌失效` 而不是删行。
9. **数据库**：只有测试环境可连库（含只读）；`db_update`/delete/insert 必须在**用例拆分阶段**先经用户确认，并配恢复方案——细则见第 5 节。

## 5. 数据库操作约束（硬性，违反即拒绝执行）

### 5.1 只有测试环境允许连库

| 环境 | 是否允许 | 说明 |
| --- | --- | --- |
| 测试环境（`ENV=测试环境`，`https://test-admin.gsrtech.com`） | ✅ 允许 | 只有这一套库可以连 |
| 预生产 / 生产 / UAT / 客户演示环境 | ❌ 禁止 | **包括只读查询**，不是"只读就没事" |

判定顺序：`.env` 的 `ENV` → `api/config/setting.py` 的 `ENV` → 接口/页面 host。任一显示非测试环境 → 视为不允许。
代码护栏：`api/common/database.py::connect()` 会校验 `setting.DB_ALLOWED_ENVS`（默认 `测试环境`），
不在白名单直接抛错。**不要为了跑通去改这个白名单或绕开 connect()。**
环境不确定时先问用户，不要试探。

### 5.2 写操作必须在「用例拆分阶段」先问用户

写操作 = `INSERT` / `UPDATE` / `DELETE` / 任何 DDL。

- **时机**：阶段 1/2，**写进用例文件之前**就问，不是执行时才补一句。
- **要说明**：目标表、影响范围（where 条件）、改动前后值、是否影响其他客户/其他用例、出错如何恢复。
- **确认物**：用户明确回复"可以"，并把该写操作登记到 `docs/requirements/<需求>.md` 的「数据与前置」节。
- **一律禁止**：无 `where` 的全表增删改、`ALTER` / `DROP` / `TRUNCATE`、修改真实客户数据、跨客户批量改。
- **执行时**：日志会打 `[DB写操作]` 前缀，报告里要能对上号；跑完必须按清理方案恢复。

### 5.3 只读查询也有限制

- 只针对测试环境；避免大表 `SELECT *`（带 `where` / `limit`）。
- 查出来的真实客户名、员工姓名、证件号等**不要原样写进缺陷单/文档**，必要时打码。

### 5.4 标准确认话术（AI 必须先说这段，再写用例）

```
本次用例需要写数据库，请确认：
- 表：gsr_xxx（主键 xxx_id）
- 操作：UPDATE gsr_xxx SET yyy='...' WHERE xxx_id=...
- 影响：预计 N 行（客户 528 / 单据 SAL-...）；是否影响其他客户：否
- 恢复：执行后改回原值 / 已配清理用例：<用例ID>
- 环境：测试环境（ENV=测试环境）
确认可以写吗？
```

### 5.5 直接拒绝的情形

1. 环境不是测试环境；
2. 写操作未经用户确认，或没有恢复方案；
3. SQL 没有 `where`、是 DDL、或跨客户批量修改。

遇到以上任一情况：**拒绝执行并说明原因**，不许"先跑后解释"。

## 6. 常见任务索引

| 任务 | 去哪里改 |
| --- | --- |
| 加接口用例集 | `api/testcase/*.xlsx` + `api/config/setting.py::TEST_FLIELOADS` |
| 加接口动作（新 method） | `api/common/executor.py` 加 `elif method == 'xxx':`（lint 会自动识别） |
| 加 UI 用例集 | `ui/testcases/**/*.yaml` + `ui/config/settings.py::PROJECT_CONFIGS` |
| 加页面对象 | `ui/pages/<page>.py` + `PAGE_CLASSES` / `PAGE_URLS` |
| 加元素定位器 | `ui/config/locators/<项目>.yaml`（先跑 `tools/ui_capture.py`） |
| 改提单格式 | `tools/evidence_bug.py::build_steps_html()` |
| 改提单过滤规则 | `tools/zentao_report.py::classify()` / `main()` 的 `--repeat` |
| 改禅道字段 | `core/zentao.py::create_bug()`（`.env` 的 `ZENTAO_*`） |
| 采集证据（自定义场景） | `ui/utils/evidence.py::EvidenceRecorder`，参考 `tools/demo_pkg_search.py` |
| 看报告 | `reports/`（allure-results / results / logs / screenshots / evidence / zentao） |

## 7. 已知坑（踩过的，别再踩）

| 现象 | 真相 / 处理 |
| --- | --- |
| 接口 110106 / UI 页面"暂无数据" | 多半是 token 过期或权限缓存；先换 `ACCESS_TOKEN_ADMIN` |
| 新扫码的会话反而没权限 | 权限缓存问题（已提单），跑 UI 用 `.env` token 注入，别用扫码会话 |
| 禅道影响版本报"不能为空" | `openedBuild` 必须数组 `["trunk"]` |
| 禅道附件传不上去 | REST `/files` 被服务端拒；走页面表单 `core/zentao_ui.py` |
| 禅道改单没生效 | 用 `PUT`，`PATCH` 静默无效 |
| 禅道删除后还能查到 | 软删除，需后台回收站 |
| 步骤里 `<img {id}.png>` 不显示 | 该版本不渲染，截图挂附件、正文注明文件名 |
| UI 表格"列表为空"判成 2 行 | antd 占位行被当数据行，过滤 `ant-table-placeholder/measure-row` |
| `Sync API inside the asyncio loop` | 同线程二次开 `sync_playwright`；放独立线程 |
| `conditionalActivation` 导致审批流不生效 | 假勤模板 deploy 时必须传 `0` |
| `${var}` 在 UI 用例里不生效 | UI 只认 `{var}`；要字面量写 `{{var}}`（`VariableStore.render` 支持转义） |

## 8. 文档地图

| 文件 | 用途 |
| --- | --- |
| `AGENTS.md`（本文件） | 总流程与约束，开工先读 |
| `PROMPT_bug_filing.md` | 提单硬约束（能不能提 / 单据段落 / 字段 / 禁区 / 自检清单） |
| `README.md` | 框架说明：目录、配置全表、命令、用例清单、方法速查、变更记录 |
| `api/README.md` | 接口用例写法（列定义、动作表、断言、变量、薪资包相关） |
| `ui/README.md` | UI 用例写法（YAML 步骤、动作、定位、扫码登录） |
| `api/variable/all.yaml` | 接口全局变量（`headers_admin` / `headers_user` 等） |
| `docs/requirements/` | 需求拆分产物（按 `docs/需求拆分模板.md` 填） |
| `docs/项目资料/公共/测试数据.md` | 环境账号、客户/供应商/员工、DB 常用表（造数前先看） |
| `docs/项目资料/<项目>/` | 接口文档 / 数据库表结构 / 需求文档 / 测试数据（含 `测试数据/README.md`） |
| `docs/需求拆分模板.md` / `docs/用例编写模板.md` | 阶段 1 / 阶段 2 的产物模板 |

## 9. 交付汇报模板（每次任务结束按这个回）

```text
1) 需求/范围：<需求名>，覆盖 R1..Rn；未覆盖：<项 + 原因>
2) 用例：接口 <n> 条（文件）、UI <n> 条（文件）；lint：0 错误
3) 执行：通过 <x> / 失败 <y> / 跳过 <z>；耗时 <>；结果文件 <路径>
4) 失败判定：<用例> → 产品缺陷 / 用例问题 / 环境问题（附证据：接口+返回 / 截图 / 日志）
5) 提单：<单号+链接>（或"按规则不提，清单见下"）
6) 待确认/待清理：<软删除单号、token 更新、未覆盖项>
```
