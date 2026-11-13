# payroll 项目资料索引

覆盖范围：算薪（薪资包）、结算包、收款包、薪资导入校验、国家模板。

## 目录

| 目录 | 放什么 |
| --- | --- |
| `接口文档/` | Swagger/OpenAPI 导出、接口说明 md、抓包整理 |
| `数据库表结构/` | 建表语句、`SHOW CREATE TABLE` 导出、字段含义 |
| `需求文档/` | PRD、原型截图、评审纪要 |
| `测试数据/` | 客户/员工/单据导出（xlsx、csv、sql）、页面截图 |

## 已收录清单

| 日期 | 文件 | 用途 |
| --- | --- | --- |
| 2026-11-12 | `数据库表结构/payroll表结构.txt` | 55 张 payroll/结算/收款相关表建表语句（字段带 COMMENT） |
| 2026-11-13 | `测试数据/README.md` | 本项目可用单据号与造数口径（已整理，随环境更新） |
| 2026-11-13 | （待补充） | 其他资料放进来后在这里登记一行 |

## 已验证接口（实测，可作为写用例的依据）

| 方法 | 路径 | 说明 | 备注 |
| --- | --- | --- | --- |
| GET | `/api/center/payrollSalaryPackage/list` | 薪资包列表 / 按 `payrollSalaryPackageCode` 查询 | 需 `center:payrollSalaryPackage:list` |
| POST | `/api/payrollCalculation/payrollCollect/importPayroll` | 导入薪资结果（导入校验） | 返回 `data.x`/`data.y`/`data.importIssues` 用于导入校验断言 |
| POST | `/api/center/payrollSalaryPackage/add` | 创建薪资包 | 只返 code/msg，不返 ID，需用 list 反查 |
| PUT | `/api/center/payrollSalaryPackage/packageVoided` | 作废薪资包 | 需 remove 权限；已作废再作废返回 200（幂等） |
| GET | `/api/center/payrollSalaryPackageRule/list` | 薪资包规则列表 | 同角色下该接口权限正常，可用于权限对比 |
| POST | （结算包确认上传）`confirmImport` | 结算包确认 | 需提交 `excelDistrictDataMap`/`countDataMap`，纯 Excel 驱动做不了 |

> 这些是历史实测结论，接口/字段变更后请更新本表；**路径与参数以 `接口文档/` 里的官方文档为准**，没有文档时以抓包为准并回填这里。

## 关键表与主键（写 `db_select` 前先看这里）

| 表 | 主键 | 说明 |
| --- | --- | --- |
| `gsr_payroll_salary_package` | `payroll_salary_package_id` | 薪资包 |
| `gsr_payroll_salary` | `payroll_salary_id` | 薪资单；`source_system` 0 系统创建 / 1 手动 / 2 RPA |
| `gsr_payroll_salary_package_rule` | `payroll_salary_package_rule_id` | 薪资包规则 |
| `gsr_settlement_client` | `settlement_client_id` | 结算客户 |
| `gsr_employee_tag` | `tag_id` | 员工标签 |

## 待补

- [ ] 薪资包/结算包相关接口的完整参数说明（Swagger 导出）
- [x] `gsr_payroll*` 系列表结构（`数据库表结构/payroll表结构.txt`）
- [ ] 各表状态字段的枚举字典（如 `payroll_status`、`data_flag` 的取值含义）
- [ ] 国家模板（France/Canada）指标编号对照表
