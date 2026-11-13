# legacy/ —— 停用的历史文件（保留可回溯，不参与执行与 lint）

`run.py lint` / `run.py api` / `run.py ui` 都不会扫描本目录；
这里放的是合并前后被替换掉的旧文件，确认没人用之后可以再删。

| 文件 | 来源 | 为什么停用 |
| --- | --- | --- |
| `salary_payment_collection.yaml` | `ui/testcases/eor_salary_ettlement/`（原 ui_playwright 框架） | 已被 `salary_payment_collection_v2.yaml` 取代，`ui/config/settings.py::PROJECT_CONFIGS["薪资结算包收款包链路"]` 指向 v2，旧文件不再被加载 |
| `test_approval_auto_approved_原始命名备份.xlsx` | `api/testcase/` | 只是「审批流或签自动通过」用例改名前的手工备份，`TEST_FLIELOADS` 里注册的是 `test_approval_auto_approved.xlsx`；留在 testcase/ 会被 lint 当作用例集统计（虚增条数） |

恢复方式：`git mv legacy/<文件> <原目录>/`，再按 AGENTS.md 第 6 节改注册表。
