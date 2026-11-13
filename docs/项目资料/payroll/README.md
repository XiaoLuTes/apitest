# payroll 项目资料索引

覆盖范围：算薪（薪资包）、结算包、收款包、薪资导入校验、国家模板。

## 目录

| 目录 | 放什么 |
| --- | --- |
| `接口文档/` | Swagger/OpenAPI 导出、接口说明 md、抓包整理 |
| `数据库表结构/` | 建表语句、`SHOW CREATE TABLE` 导出、字段含义 |
| `需求文档/` | PRD、原型截图、评审纪要 |
| `测试数据/` | 客户/员工/单据导出、导入模板、页面截图 |
| `历史用例/` | 往期 Excel 用例（回归基线与写法参考） |

## 已收录清单

| 日期 | 文件 | 用途 |
| --- | --- | --- |
| 2026-11-12 | `数据库表结构/payroll表结构.txt` | 55 张 payroll/结算/收款相关表建表语句（字段带 COMMENT） |
| 2026-11-13 | **`接口文档/接口清单.md`** | **payroll 接口总清单**：约定/错误码/12+ 接口/字段说明/已封装能力（来源标注 ✅实测·📄整理） |
| 2026-11-13 | `接口文档/20261113-桌面-payroll接口整理.md` | 原始整理稿（含国家模板导出、confirmImport 完整报文样例） |
| 2026-10-14 | `接口文档/20261014-样例-薪资包列表接口返回.json` | 真实接口返回样例（字段结构参考） |
| 2026-11-13 | **`数据库表结构/表关系速查.md`** | **41 张表按域分类：主键 / 关联字段 / 表注释 + 对账链路 + db_select 注意事项**（自动解析生成） |
| 2026-09-21 | `数据库表结构/20260921-桌面-对账中心查询链路.txt` | 对账中心多表查询链路原始稿 |
| 2026-11-13 | `需求文档/20261113-历史-支持薪资包发起结算-需求人话版解读.html` | 薪资包发起结算需求解读 |
| 2026-11-13 | `需求文档/20261113-历史-支持薪资包发起结算测试点.xmind` | 该需求测试点脑图 |
| 2026-07-29 | `需求文档/20260729-历史-客户端算薪任务需求文档.docx` | **客户端算薪任务 PRD（3.8 MB）** |
| 2026-11-02 | `需求文档/20261102-历史-GSR报销系统需求文档v5.0.docx` | **报销系统 PRD v5.0 评审修订版（4.1 MB）** |
| 2026-09-21 | `需求文档/20260921-历史-客户端对账中心需求.docx` | 客户端对账中心需求 |
| 2026-08-20 | `需求文档/20260820-历史-薪资单发放优化需求.xmind` | 薪资单发放优化需求脑图 |
| 2026-11-13 | `历史用例/20261113-历史-支持薪资包发起结算测试用例-V2.xlsx` | **与我们「薪资包结算」用例集同需求的历史用例，可对照覆盖度** |
| 2026-11-13 | `历史用例/20261113-历史-支持薪资包发起结算-用例导入稿.xlsx` | 禅道用例导入稿 |
| — | `历史用例/对账管理测试用例.xlsx`、`客户端对账中心测试用例.xlsx`、`客户端算薪任务测试用例.xlsx` | 往期用例参考 |
| 2026-11-13 | `测试数据/README.md` | 本项目可用单据号与造数口径（已整理，随环境更新） |
| 2026-11-13 | `测试数据/` 下 `payroll-导入模板示例.xls(x)`、`CPP*.xlsx`、`导入模板-{AdHoc,Bonus,Reimbursement}.xlsx` | 薪资导入双向模板与真实导出样例 |
| 2026-11-13 | （待补充） | 其他资料放进来后在这里登记一行 |

## 接口总清单

完整版见 **`接口文档/接口清单.md`**（含通用约定、错误码、状态取值、国家模板异步下载链路、importPayroll / confirmImport 报文、结算包审批）。

## 已验证接口（实测速查）

| 方法 | 路径 | 说明 | 备注 |
| --- | --- | --- | --- |
| GET | `/api/center/payrollSalaryPackage/list` | 薪资包列表 / 按 `payrollSalaryPackageCode` 查询 | 需 `center:payrollSalaryPackage:list` |
| POST | `/api/payrollCalculation/payrollCollect/importPayroll` | 导入薪资结果（导入校验） | 返回 `data.x`/`data.y`/`data.importIssues` 用于导入校验断言 |
| POST | `/api/center/payrollSalaryPackage/add` | 创建薪资包 | 只返 code/msg，不返 ID，需用 list 反查 |
| PUT | `/api/center/payrollSalaryPackage/packageVoided` | 作废薪资包 | 需 remove 权限；已作废再作废返回 200（幂等） |
| GET | `/api/center/payrollSalaryPackageRule/list` | 薪资包规则列表 | 同角色下该接口权限正常，可用于权限对比 |
| POST | （结算包确认上传）`confirmImport` | 结算包确认 | 需提交 `excelDistrictDataMap`/`countDataMap`，纯 Excel 驱动做不了 |

> 这些是历史实测结论，接口/字段变更后请更新本表；**路径与参数以 `接口文档/` 里的官方文档为准**，没有文档时以抓包为准并回填这里。

## 关键表与主键（完整版见 `数据库表结构/表关系速查.md`，41 张表按域分类）

| 表 | 主键 | 说明 |
| --- | --- | --- |
| `gsr_payroll_salary_package` | `payroll_salary_package_id` | 薪资包 |
| `gsr_payroll_salary` | `payroll_salary_id` | 薪资单；`source_system` 0 系统创建 / 1 手动 / 2 RPA |
| `gsr_payroll_salary_package_rule` | `payroll_salary_package_rule_id` | 薪资包规则 |
| `gsr_settlement_client` | `settlement_client_id` | 结算客户 |
| `gsr_employee_tag` | `tag_id` | 员工标签 |

## 未收录的大文件（在桌面/workspace，需要时手动放进来）

| 文件 | 大小 | 说明 |
| --- | --- | --- |
| `payroll+结算/8.24payroll算薪任务-客户端接口性能测试报告.docx` | 6.6 MB | 性能报告（需要时再放） |
| `payroll+结算/payroll算薪任务.xmind`、`cspayroll对账管理.xmind` | 0.3~0.4 MB | 脑图（peter 版） |
| `payroll+结算/主账号上传.xlsx`、`子账号上传.xlsx` | 各 134 KB | 上传用例数据 |

## 待补

- [x] 薪资包相关接口整理（`接口文档/接口清单.md`，来源标注实测/整理）
- [ ] 结算包 / 收款包 / 对账中心接口 + 完整 Swagger 导出
- [x] `gsr_payroll*` 系列表结构（`数据库表结构/payroll表结构.txt`）
- [ ] 各表状态字段的枚举字典（如 `payroll_status`、`data_flag` 的取值含义）
- [ ] 国家模板（France/Canada）指标编号对照表
