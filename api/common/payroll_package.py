"""薪资包管理（管理端 Payroll → 算薪 → 薪资包管理）查询便捷方法

把「按薪资包ID查询」这类高频动作做成框架方法，用例/脚本/AI 生成时直接调用，
不用每次手拼 URL、header 和分页参数。

实测（2026-11-13）：
    GET {管理端}/api/center/payrollSalaryPackage/list
        ?pageSize=20&pageNum=1[&payrollSalaryPackageCode=SAL-20261112-0001][&settlementPackageCode=..]
        [&payPagType=1][&supplierId=107][&country=Canada][&payrollStatus=0]
    Header: Authorization: Bearer <ACCESS_TOKEN_ADMIN>（浏览器登录态 token，见 .env）
    返回: {"total": 1, "rows": [{...}]}（成功时无 code/msg 包装；无权限时返回 code=110106）

用法：
    from api.common.payroll_package import get_salary_package, query_salary_packages

    row = get_salary_package("SAL-20261112-0001")          # 取不到返回 None
    row["payrollStatus"], row["employeeCount"]
    page = query_salary_packages(payPagType="1", pageSize=5)  # 原始分页结构
"""
import os

import requests

from api.config.setting import setting

LIST_PATH = "/api/center/payrollSalaryPackage/list"

# 常用字段（写进变量的变量名 → 接口字段名）
VARIABLE_FIELDS = {
    "pkg_id": "payrollSalaryPackageId",
    "pkg_code": "payrollSalaryPackageCode",
    "pkg_type": "payPagType",
    "pkg_supplier_id": "supplierId",
    "pkg_supplier": "supplierName",
    "pkg_country": "country",
    "pkg_service_month": "serviceMonth",
    "pkg_employee_count": "employeeCount",
    "pkg_status": "payrollStatus",
    "pkg_settle_code": "settlementPackageCode",
    "pkg_source": "sourceSystem",
    "pkg_lock_time": "lockTime",
}

# 允许直接当查询条件传给接口的过滤字段（其余参数会作为额外 query 透传）
FILTER_FIELDS = (
    "payrollSalaryPackageCode", "settlementPackageCode", "payPagType",
    "supplierId", "country", "payrollStatus", "serviceMonth", "clientId",
)


def admin_token(token=None):
    """取管理端 token：优先入参，其次 .env 的 ACCESS_TOKEN_ADMIN"""
    token = token if token is not None else setting.ENV_VARIABLES.get("access_token_admin", "")
    if not str(token or "").strip():
        raise RuntimeError(
            "缺少管理端 token：请在 .env 配置 ACCESS_TOKEN_ADMIN（浏览器登录后拷 GSR-Token cookie 的值）")
    return str(token).strip()


def admin_headers(token=None):
    return {
        "Authorization": "Bearer " + admin_token(token),
        "Accept": "application/json, text/plain, */*",
        "Connection": "keep-alive",
    }


def query_salary_packages(token=None, timeout=None, **filters):
    """按任意条件查询薪资包列表，返回接口原始结构 {"total": n, "rows": [...]}

    :param filters: payrollSalaryPackageCode / settlementPackageCode / payPagType /
                    supplierId / country / payrollStatus / serviceMonth / pageSize / pageNum ...
    """
    url = setting.TEST_URL["管理端"] + LIST_PATH
    params = {"pageSize": filters.pop("pageSize", 20), "pageNum": filters.pop("pageNum", 1)}
    params.update({k: v for k, v in filters.items() if v is not None and v != ""})
    resp = requests.get(url, params=params, headers=admin_headers(token),
                        timeout=timeout or setting.HTTP_TIMEOUT)
    resp.raise_for_status()
    data = resp.json()
    if isinstance(data, dict) and data.get("code") not in (None, 200):
        # 无权限(110106) / token 失效 等业务错误，直接把服务端信息抛出来，避免被当成"查不到"
        raise RuntimeError(f"薪资包查询失败：code={data.get('code')} msg={data.get('msg')}")
    return data


def get_salary_package(package_code, token=None, **filters):
    """按薪资包ID精确查询，返回首条记录（dict）；查不到返回 None"""
    data = query_salary_packages(token=token, payrollSalaryPackageCode=package_code, **filters)
    rows = (data or {}).get("rows") or []
    return rows[0] if rows else None


def require_salary_package(package_code, token=None, **filters):
    """同 get_salary_package，但查不到时直接断言失败（用例里想要"必须存在"时用）"""
    row = get_salary_package(package_code, token=token, **filters)
    if row is None:
        raise AssertionError(f"未查询到薪资包：{package_code}")
    return row


def package_variables(row):
    """把一行记录转成框架变量字典（键见 VARIABLE_FIELDS），executor 的 pkgquery 用它回填变量"""
    row = row or {}
    return {var: row.get(field) for var, field in VARIABLE_FIELDS.items()}


def assert_row_fields(row, expect, case_id=""):
    """把 "字段=值[,字段=值]" 形式的期望值与记录逐项比对（executor 的 pkgquery 用）

    支持用框架变量名（pkg_status）或接口字段名（payrollStatus）指定字段
    """
    from api.common.variable_handle import VariableHandle  # 延迟导入，避免循环依赖

    row = row or {}
    alias = dict(VARIABLE_FIELDS)
    details = []
    for part in str(expect).split(","):
        if not part.strip():
            continue
        if "=" not in part:
            raise AssertionError(f"断言格式应为 字段=值，当前：{part}")
        key, _, expected = part.partition("=")
        key, expected = key.strip(), expected.strip()
        field = alias.get(key, key)
        actual = row.get(field)
        same, way = VariableHandle.compare_value(actual, expected)
        details.append(f"{key}({field}) 期望 {expected} 实际 {actual}（{way}）")
        if not same:
            raise AssertionError(
                f"用例 {case_id} 薪资包字段断言失败：{key} 期望 {expected} 实际 {actual}")
    return details


__all__ = [
    "LIST_PATH", "VARIABLE_FIELDS", "FILTER_FIELDS",
    "admin_token", "admin_headers", "query_salary_packages",
    "get_salary_package", "require_salary_package",
    "package_variables", "assert_row_fields",
]
