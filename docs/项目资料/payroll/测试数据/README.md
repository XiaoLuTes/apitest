# payroll 测试数据

> 环境、账号、客户/供应商/员工等**跨项目公共数据**见 `../../公共/测试数据.md`。
> 本文件只放 payroll 专属数据集。失效数据标 `❌失效` 不删行。

## 1. 薪资包（SAL）

| 单据号 | 关键字段 | 用途 | 状态 |
| --- | --- | --- | --- |
| `SAL-20261112-0001` | supplier 107 / Canada / `serviceMonth=202611` / `payPagType=1`(ON_CYCLE) / `payrollStatus=0`(待发起算薪) / `employeeCount=1` / `lockTime=2026-11-11` / `sourceSystem=0`(系统创建) | 薪资包列表查询（接口 + UI）基准数据 ✅实测 | 📌会变：`payrollSalaryPackageId` 曾为 2502 / 2554，**按 code 查，不要写死 id** |

用法：

```text
接口：GET /api/center/payrollSalaryPackage/list?payrollSalaryPackageCode=SAL-20261112-0001  → total=1
页面：薪资包ID 输入该值 → 列表 1 行（首行字段见上表）
```

## 2. 结算包 / 收款包（SPP、CPP）

| 单据号 | 关联 | 用途 | 状态 |
| --- | --- | --- | --- |
| `SPP202611130053` | 出现在导入校验用例的国家模板文件名里 | 薪资导入校验（未填数国家模板）✅实测 | 📌会变 |
| `SPP202611130039` | 同系列结算包号 | 历史用例使用 ⚠️待确认 | |
| `CPP202611130075` | 存量缺陷单里出现的收款包号 | 收款包相关排查 ⚠️待确认 | |

## 3. 国家模板指标编号（写薪资数据前必看）

| 指标 | 法国模板 | 加拿大模板 |
| --- | --- | --- |
| 基本薪资 | `C1` | `1` |
| 服务费 | `S1~S4` | `61~64` |
| SE1 / SE2 / G1 / H / I / J / K / L1 / L2 / M | 两边一致 | 两边一致 |

已验证算例（法国模板）：

```text
填 C1=4500, C2=100, C3=20, C4=30, C5=10, C51=0, C56=50, C57=200, C151=0, S1=100, SE1=1.15, SE2=0.87
→ A=4910，total_local_employer_cost=4269.57，total_invoice_amount=5022.49  ✅实测
```

## 4. 造数/查询口径（实测踩过）

| 场景 | 口径 |
| --- | --- |
| 创建薪资包 | `POST /api/center/payrollSalaryPackage/add` 只返 code/msg，**不返 ID**，要用 list 反查 ✅实测 |
| 结算包生成 | 异步，需轮询 list 的 `settlementPackageCodeList`（建议 `retry=20`）✅实测 |
| 作废 | `PUT /api/center/payrollSalaryPackage/packageVoided`，需 remove 权限；已作废再作废仍返回 200（幂等）✅实测 |
| 确认上传 | `confirmImport` 必须提交前端解析出的 `excelDistrictDataMap` / `countDataMap`，纯 Excel 驱动做不了 ✅实测 |
| 缺员工列表 | 缺 `payrollSalaryList` 调 add 仍返回 200 并创建 0 员工空包（疑缺陷）⚠️ |
| 导入校验 | 返回 `data.x` / `data.y` / `data.importIssues` 是断言依据 ✅实测 |
