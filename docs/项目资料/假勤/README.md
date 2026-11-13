# 假勤项目资料索引

覆盖范围：请假/加班/销假、审批链与审批人策略、审批条件（含员工标签条件）。

## 目录

| 目录 | 放什么 |
| --- | --- |
| `接口文档/` | 模板/审批链/待办接口文档、Swagger 导出、抓包整理 |
| `数据库表结构/` | 审批相关表（如 `gsr_approval_users`）、员工表字段说明 |
| `需求文档/` | PRD、审批流配置说明、评审纪要 |
| `测试数据/` | 员工/客户/标签/模板导出、审批流截图 |

## 已收录清单

| 日期 | 文件 | 用途 |
| --- | --- | --- |
| 2026-11-13 | （待补充） | 资料还没放进来，放进来后在这里登记一行 |

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

## 待补

- [ ] 假勤模板 deploy / 查询模板详情的接口路径与 body 结构
- [ ] `gsr_approval_users`、审批实例/任务表的完整字段
- [ ] 请假额度计算规则（销假回补口径）
