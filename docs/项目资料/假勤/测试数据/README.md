# 假勤 / 审批流 测试数据

> 环境、账号、客户等**跨项目公共数据**见 `../../公共/测试数据.md`。
> 本文件只放假勤+审批流专属数据（员工标签条件、审批人策略、模板版本）。失效标 `❌失效`。

## 1. 员工标签数据（审批条件「员工标签」用）

| 项 | 值 | 说明 |
| --- | --- | --- |
| 标签组 | `52` —「DS自动化接口测试」（clientId 528） | 自定义标签组 ✅实测 |
| 标签 | `122`、`123` | 组 52 下的两个标签 ✅实测 |
| 系统标签组 | `1`（含标签 `74`） | 用于「包含全部」的跨组前置（保证页面可达）✅实测 |
| 已打标签员工 | `3608` → tag `122` | `employee_tag_version=1` ✅实测 |
| 打标签接口 | `PUT /api/center/externalEmployeeInfo/employeeTags/{id}` | body `{employeeIds, tagIds, version}`；版本不一致返回 `100007`「员工标签已被修改」✅实测 |
| 标签查询接口 | `GET /api/center/externalEmployeeInfo/employeeTags/{employeeId}`、`/filterTree` | 需管理端「小卢」类账号权限，否则 `110106` ✅实测 |

## 2. 审批模板与开关

| 项 | 值 | 说明 |
| --- | --- | --- |
| 假勤模板 | `ATC2025122400242`（当前 v109） | `node_s1`/`node_s2` 均 `approvalMode=1`（或签）✅实测 |
| 通用模板 | `ATC2025123000251` | `templateType=-1`；`conditionalActivation=1` 时假勤回落到它（审批人为 272）✅实测 |
| `conditionalActivation` | **必须传 `0`** | 传 `1` 或不传：假勤模板不生效、条件不求值恒走第一分支 ✅实测 |
| 报销模板限制 | `templateType=4`（报销）**不支持员工标签条件** | 前端 bundle 里该字段只在 `templateType !== 4` 时加入 ✅实测 |

## 3. 审批人数据（验证"审批人为空/兜底"策略用）

| 项 | 值 | 说明 |
| --- | --- | --- |
| 全局指定审批人 | `361` — jack@gsrtech.com | 必须是全局审批人（`client_id=None`）✅实测 |
| 兜底审批人 | `382` | 策略 1/2 下空审批人会转给它 ✅实测 |
| 策略 3 目标 | `381` | 真实空来源（报销档案角色未配置）时转它待审 ✅实测 |
| 跨客户审批人 | `271`（`client_id=551`） | **不会被过滤**，仍生成待办 ⚠️与"按 client_id 过滤"的旧结论不一致，待产品确认 |
| 空邮箱审批人 | `180` | 不会被过滤，仍 status=1 待审 ✅实测 |
| 错域名审批人 | `380` — louie.lu@hsrtech.com | 不会被过滤 ✅实测 |
| 本客户审批人 | `337` | deploy 时会报错（必须传全局审批人）✅实测 |

## 4. 造数口径（实测踩过）

| 场景 | 口径 |
| --- | --- |
| 假勤「审批人为空」 | `assignedType=1` + `assignedUsers=[]` —— **属接口造数，前端指定人员是必填、页面造不出来** ✅实测 |
| 策略差异 | 同为空数组：策略 1/2 转兜底 382 待审；**策略 3 静默自动通过**（节点 status=2、无任务） ✅实测 |
| 销假 | 销假单也走审批；两节点都通过额度才回补；**同一时段销假后仍不可重提，重跑必须换日期段** ✅实测 |
| 展示节点 | 假勤跳过展示节点只保留 `status=11`，不写占位审批人（与报销不同）✅实测 |
| 驳回 | 必须 `POST /api/center/template/reject/task/{taskId}`（body `{comment}`），GET 返回 `100003` ✅实测 |

## 5. 常用查询口径

| 目的 | 接口 |
| --- | --- |
| 查审批链（谁在审） | `GET /api/center/template/get/approval/path/{instanceId}` → `node.props.approverProperties.assignedUsers`（含 id/name/workEmail/status/taskId） |
| 查是否有待办 | `GET /api/center/template/find/task/instance/name/{instanceId}` |
| 查标签树（按客户隔离） | `GET /api/center/externalEmployeeInfo/employeeTags/filterTree`；停用/删除标签会被过滤 |
