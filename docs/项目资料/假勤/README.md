# 假勤项目资料索引

覆盖范围：请假/加班/销假、审批链与审批人策略、审批条件（含员工标签条件）。

## 目录

| 目录 | 放什么 |
| --- | --- |
| `接口文档/` | 模板/审批链/待办接口文档、Swagger 导出、抓包整理 |
| `数据库表结构/` | 审批相关表（如 `gsr_approval_users`）、员工表字段说明 |
| `需求文档/` | PRD、审批流配置说明、评审纪要 |
| `测试数据/` | 员工/客户/标签/模板导出、审批流截图 |
| `历史用例/` | 往期 Excel 用例（回归基线与写法参考） |

## 已收录清单

| 日期 | 文件 | 用途 |
| --- | --- | --- |
| 2026-11-12 | `数据库表结构/考勤各表结构.txt` | 35 张考勤/请假/审批相关表建表语句（字段带 COMMENT） |
| 2026-11-13 | `接口文档/20261113-桌面-审批流模板接口.md` | 审批模板接口入参（`templateType`/`dataStructure`/`customerIds`），账号已脱敏 |
| 2026-11-13 | `需求文档/20261113-历史-自定义审批流程.xmind` | 自定义审批流程需求脑图 |
| 2026-11-13 | `需求文档/20261113-历史-加班时长新增规则-测试点.xmind` | 加班时长新增规则 + 日报月报更新测试点 |
| 2026-11-13 | `历史用例/20261113-历史-自定义审批流程测试用例.xlsx` | 审批流往期用例（审批人/条件写法参考） |
| 2026-03-30 | `历史用例/20260330-历史-请假加班记录汇总及导入测试用例.xlsx` | 请假/加班汇总与导入 |
| 2026-03-31 | `历史用例/20260331-历史-请假时长优化测试用例.xlsx` | 请假时长计算优化 |
| 2026-10-28 | `历史用例/20261028-历史-报销系统审批测试用例v3.0.xlsx` | 报销审批（含员工标签相关场景） |
| 2026-11-13 | `测试数据/README.md` | 本项目可用单据号与造数口径（已整理，随环境更新） |
| 2026-11-13 | `测试数据/考勤打卡-多配置-用例参考.xlsx`、`生产-测试数据3.xlsx` | 打卡多配置用例参考、生产样本数据（含真实客户名，勿外传） |
| 2026-11-13 | （待补充） | 其他资料放进来后在这里登记一行 |

## 已验证接口（实测）

| 方法 | 路径 | 说明 | 备注 |
| --- | --- | --- | --- |
| POST | `/api/center/template/reject/task/{taskId}` | 审批驳回 | body `{comment}`；**必须 POST**，GET 会返回 100003 |
| GET | `/api/center/template/get/approval/path/{instanceId}` | 查询审批链 | 审批人在 `node.props.approverProperties.assignedUsers`（含 id/name/workEmail/status/taskId） |
| GET | `/api/center/template/find/task/instance/name/{instanceId}` | 查待办 | 用于确认节点是否生成待办 |
| GET | `/api/center/externalEmployeeInfo/employeeTags/{employeeId}` | 查员工标签 | 需管理端「小卢」类账号权限，否则 110106 |
| GET | `/api/center/externalEmployeeInfo/employeeTags/filterTree` | 标签树（按客户隔离） | 停用/删除标签会被过滤 |
| GET | `/api/center/employeeTag/list` | 标签列表 | 任何 clientId 都返回 200，`data` 可能为 null |
| PUT | `/api/center/externalEmployeeInfo/employeeTags/{id}` | 打标签 | body `{employeeIds, tagIds, version}`，版本冲突返回 100007 |

## 关键配置口径（实测，写用例前必读）

| 项 | 取值 | 说明 |
| --- | --- | --- |
| 假勤模板 | `ATC2025122400242`（当前 v109） | `node_s1`/`node_s2` 均为 `approvalMode=1` 或签 |
| 通用模板 | `ATC2025123000251` | `templateType=-1`，`conditionalActivation=1` 时假勤回落到这个模板 |
| `conditionalActivation` | 必须传 `0` | 传 1 或不传会导致条件不求值 / 模板不生效 |
| 审批人 | 361（jack@gsrtech.com，全局指定）、382（兜底）、381 | 自定义指定审批人必须是**全局审批人**（`client_id=None`），传本客户账号会 deploy 报错 |
| 空审批人 | `assignedType=1` + `assignedUsers=[]` 属接口造数 | 前端指定人员是必填，页面造不出来，验证策略时注意 |

## 关键表与主键（写 `db_select` 前先看这里）

| 表 | 主键 | 说明 |
| --- | --- | --- |
| `gsr_employee_leave_info` | **`gsr_employee_info_id`** | 请假单（主键名与表名不一致，别写 `leave_info_id`） |
| `atc_ru_instance` | `instance_id` | 审批实例 |
| `atc_ru_task` | `task_id` | 审批任务 |
| `atc_re_template` | `template_id` | 审批模板 |
| `gsr_external_employee_normal_info` | `external_employee_normal_info_id` | 员工（公共表） |

## 未收录的大文件（在桌面/workspace，需要时手动放进来）

| 文件 | 大小 | 说明 |
| --- | --- | --- |
| — | — | 报销系统 PRD v5.0 已归到 `../payroll/需求文档/20261102-历史-GSR报销系统需求文档v5.0.docx` |
| `假勤需求/4.1.0/PRD-假勤系统-排班开放客户端、排班日期类型标记.docx` | 1.5 MB | 排班 PRD |
| `假勤需求/假勤系统重构/假勤系统重构.xmind`、`考勤打卡（多配置）V2.0版本.xmind` | 0.5~0.7 MB | 重构/打卡脑图 |
| `假勤需求/测试报告/V3.30.10 假勤申请管理测试报告.docx` | 0.45 MB | 往期测试报告 |
| `假勤需求/考勤打卡/生产数据/*.xlsx` | 30 KB/个 | 生产客户数据（含企业名，谨慎） |

## 待补

- [ ] 假勤模板 deploy / 查询模板详情的接口路径与 body 结构
- [x] 审批实例/任务表（`atc_ru_instance` / `atc_ru_task` 已在 `数据库表结构/考勤各表结构.txt`）
- [ ] `gsr_approval_users` 的完整字段（主键已知为 `gsr_approval_users_id`）
- [ ] 请假额度计算规则（销假回补口径）
