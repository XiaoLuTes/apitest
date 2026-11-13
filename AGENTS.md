# AGENTS.md —— 自动化测试执行手册（每个 AI 对话开工前先读）

> 本文件是**唯一入口**：读完它就能从「拿到需求」一路做到「执行完 + 禅道提单」。
> 细节文档在 `README.md`；提单硬约束在 `PROMPT_bug_filing.md`（提单前必须再读一遍）。
> 本文件约定 > 临时想法。与代码冲突时，以代码现状为准，并顺手更新本文件。

---

## 0. 一句话现状

- 框架：`D:\lu\pycharm\autotest`（接口 `api/` + UI `ui/` + 公共层 `core/`，统一入口 `run.py`）
- 原始两个框架 `D:\lu\pycharm\api`、`D:\lu\pycharm\ui_playwright` **保持原样，禁止改动**（只读参考）
- 测试环境：业务平台 `https://test-admin.gsrtech.com`；禅道 `http://172.21.100.100:8101/zentao`
- 执行方式：`python run.py <子命令>`（在 `D:\lu\pycharm\autotest` 下执行）

## 1. 开工前 30 秒检查

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

---

## 2. 端到端流程（六段，每段都有产物与人工闸口）

### 阶段 1 —— 需求拆分（输入：PRD/文档/截图/禅道需求号）

要做的事：
1. 提取**业务规则**、状态流转、权限差异、边界与异常、数据依赖。
2. 判断改动影响面：涉及哪些页面、哪些接口、哪些历史用例需要回归。
3. 产出 `docs/requirements/<需求名>.md`：
   - 需求摘要（一句话）
   - 规则矩阵（规则编号 R1、R2…）
   - 测试点清单（测试点编号 → 覆盖哪条规则 → 接口层/UI 层/不可自动化）
   - 未覆盖项 + 原因（明确写出来，别默默漏掉）
4. 需求不清晰时：**照样列测试点并在文档里标注"待确认"**，不要停下来等；公司口径是"多提、可去重、允许噪音"。
   前端造不出来的非法数据/脏数据**不做**接口健壮性用例（只验证前端有拦截即可）。

🚦 人工闸口：把「测试点清单」给用户过一眼（10 分钟）。用户说"可以"再进阶段 2。

### 阶段 2 —— 用例设计（接口 + UI 双轨）

先按层拆分：
- 纯后端逻辑、参数校验、数据落库、状态字段 → **接口层**
- 页面展示、交互流程、元素状态、前端校验提示 → **UI 层**
- 同一规则两层都值得验时，两层都写（接口验数据、UI 验呈现）

接口层（Excel 驱动）：
- 文件放 `api/testcase/test_<主题>.xlsx`，三个 sheet：`数据准备` / `测试执行` / `数据清理`
- 列：`case_id, name, headers, method, url, data, response, extract, validata, result`（建议再加 `备注`、`retry`）
- `name` 以「管理端｜/员工端｜」开头（决定请求打哪个 host）
- 断言 `validata` 写 JSON：`{"$.code": 200, "$.data.id": "..."}`；DB 断言用 `db_select` + `字段=值`
- 详细动作与写法：`README.md` 第 8 节 + `api/README.md`
- 注册项目：`api/config/setting.py` 的 `TEST_FLIELOADS` 加一行

UI 层（YAML 驱动）：
- 文件放 `ui/testcases/<项目>/<名>.yaml`；步骤字段：`step_name / element / action / data / expected`
- 元素名必须**已存在**于 `ui/config/locators/<项目>.yaml`；没有就现场采集（见阶段 2.5）
- 注册项目：`ui/config/settings.py` 的 `PROJECT_CONFIGS`（`PAGE_NAME` / `TESTCASES_PATH` / `ELEMENT_LOCATORS` / `LOADING_SELECTOR`）
- 需要新增页面对象时：`ui/pages/<page>.py` 继承 `GsrAdminPage`，并在 `PAGE_CLASSES`、`PAGE_URLS` 注册

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

## 3. 硬约束（违反即返工）

1. **只改 `autotest/`**：`D:\lu\pycharm\api`、`D:\lu\pycharm\ui_playwright` 一律只读。
2. **凭据只在 `.env`**：不写进代码、不写进文档、不提交 git；不把账号密码贴进单据。
3. **提单格式只在 `tools/evidence_bug.py::build_steps_html()` 定义**：不要在别处拼 HTML。
4. **用例数据文件**才是一等公民：新增用例优先写 xlsx/yaml，不要为一次性场景写脚本。
5. **先 lint 再执行**；**先草稿再提交**；**先重跑再判定偶发**。
6. 报告目录（`reports/`）不进 git；`api/variable/extract.yaml` 是运行期产物，也不入库。
7. 遇到不确定的环境/权限现象：**报告用户**（附错误码与证据），不要改断言去"迁就"环境。

## 4. 常见任务索引

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

## 5. 已知坑（踩过的，别再踩）

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

## 6. 文档地图

| 文件 | 用途 |
| --- | --- |
| `AGENTS.md`（本文件） | 总流程与约束，开工先读 |
| `PROMPT_bug_filing.md` | 提单硬约束（能不能提 / 单据段落 / 字段 / 禁区 / 自检清单） |
| `README.md` | 框架说明：目录、配置全表、命令、用例清单、方法速查、变更记录 |
| `api/README.md` | 接口用例写法（列定义、动作表、断言、变量、薪资包相关） |
| `ui/README.md` | UI 用例写法（YAML 步骤、动作、定位、扫码登录） |
| `api/variable/all.yaml` | 接口全局变量（`headers_admin` / `headers_user` 等） |
| `docs/requirements/` | 需求拆分产物（测试点清单） |

## 7. 交付汇报模板（每次任务结束按这个回）

```text
1) 需求/范围：<需求名>，覆盖 R1..Rn；未覆盖：<项 + 原因>
2) 用例：接口 <n> 条（文件）、UI <n> 条（文件）；lint：0 错误
3) 执行：通过 <x> / 失败 <y> / 跳过 <z>；耗时 <>；结果文件 <路径>
4) 失败判定：<用例> → 产品缺陷 / 用例问题 / 环境问题（附证据：接口+返回 / 截图 / 日志）
5) 提单：<单号+链接>（或"按规则不提，清单见下"）
6) 待确认/待清理：<软删除单号、token 更新、未覆盖项>
```
