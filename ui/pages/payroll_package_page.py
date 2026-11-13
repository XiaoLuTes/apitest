# -*- coding: utf-8 -*-
"""Payroll → 算薪 → 薪资包管理 页面对象

路由：/center/payroll/payrollSalary/packageManagement
查询区元素（实测 2026-11-13）：
    薪资包ID   #payrollSalaryPackageCode      结算包ID #settlementPackageCode
    薪资包类型 #payPagType                    供应商   #supplierId
    国家/地区  #country                       状态     #payrollStatus
表格列：薪资包ID、薪资包类型、服务月份、供应商名称、国家/地区、员工人数、算薪日、状态、
        数据来源、结算包ID、结算包状态、操作

常用方法：
    page.open_package_management()                      # 打开页面（免扫码 token 登录）
    page.query_by_package_code("SAL-20261112-0001")     # 输入薪资包ID并点搜索，等 list 接口返回
    page.get_row_by_code("SAL-20261112-0001")           # 返回 {表头: 单元格文本}
    page.assert_package_row(code, 状态="待发起算薪")      # 断言某行的字段
    page.assert_empty()                                 # 断言列表为空（暂无数据）
"""
import re

import allure

from ui.pages.gsr_admin_page import GsrAdminPage
from ui.utils.logger import logger

PAGE_PATH = "center/payroll/payrollSalary/packageManagement"
LIST_API_KEYWORD = "/payrollSalaryPackage/list"

JS_TABLE = """
() => {
  const t = document.querySelector('.ant-table');
  if (!t) return {headers: [], rows: []};
  const headers = Array.from(t.querySelectorAll('thead th')).map(th => (th.innerText || '').trim());
  const rows = Array.from(t.querySelectorAll('tbody tr'))
      // 排除 antd 的“空数据占位行”和“测量行”，否则会被当成真实数据行
      .filter(tr => !/ant-table-placeholder|ant-table-measure-row/.test(tr.className || ''))
      .map(tr => Array.from(tr.querySelectorAll('td')).map(td => (td.innerText || '').trim()))
      // 全空行、以及只有“暂无数据/ 无数据”的占位行都不算数据行
      .filter(cells => cells.some(c => c) && !(cells.length === 1 && /^暂无数据$|^无数据$/.test(cells[0])));
  return {headers, rows};
}
"""


class PayrollPackagePage(GsrAdminPage):
    """薪资包管理页面（继承管理端登录能力）"""

    # 本页路由也要算"已登录"，否则 ensure_logged_in 会误判为未登录去扫码
    LOGGED_IN_URL = re.compile(r"/payrollSalary/packageManagement|/center/payroll|/sys|/statistics")

    # ==================== 页面动作 ====================
    @allure.step("打开薪资包管理页面")
    def open_package_management(self):
        url = self.settings.URL.rstrip("/") + "/" + PAGE_PATH
        self.open(url)
        self.wait_if_loading()
        logger.info(f"薪资包管理页面已打开: {self.page.url}")
        return self

    @allure.step("按薪资包ID查询: {package_code}")
    def query_by_package_code(self, package_code, settlement_code=None):
        """输入薪资包ID（可选结算包ID）并点击搜索，等 list 接口返回后再继续

        返回接口响应 JSON（无权限 110106 时会记 WARNING，便于区分"查不到"和"没权限"）。
        """
        self.input_text("pkg_code_input", package_code)
        if settlement_code:
            self.input_text("settlement_code_input", settlement_code)
        payload = {}
        try:
            with self.page.expect_response(
                    lambda r: LIST_API_KEYWORD in r.url and r.request.method == "GET",
                    timeout=self.settings.IMPLICIT_WAIT) as watcher:
                self.element_click("search_button")
            data = watcher.value.json()
        except Exception as e:                      # noqa: BLE001
            logger.warning(f"等待薪资包列表接口返回失败（继续按页面状态判断）: {e}")
            data = {}
        if isinstance(data, dict) and data.get("code") not in (None, 200):
            logger.warning(f"薪资包列表接口返回异常：code={data.get('code')} msg={data.get('msg')}"
                           f"（110106 通常是权限问题，不是没有数据）")
        self.wait_if_loading()
        self.page.wait_for_timeout(800)             # 等表格重绘
        logger.info(f"薪资包查询完成：{package_code}，列表 {len(self.get_table_rows())} 行")
        return data

    @allure.step("重置查询条件")
    def reset_query(self):
        self.element_click("reset_button")
        self.wait_if_loading()
        self.page.wait_for_timeout(800)
        return self

    # ==================== 数据读取 ====================
    def get_table(self):
        """返回 {headers: [...], rows: [[...], ...]}"""
        return self.page.evaluate(JS_TABLE) or {"headers": [], "rows": []}

    def get_table_rows(self):
        """返回 [{表头: 单元格文本}, ...]"""
        table = self.get_table()
        headers, rows = table.get("headers") or [], table.get("rows") or []
        return [dict(zip(headers, row)) for row in rows]

    def get_row_by_code(self, package_code):
        """按薪资包ID在表格里找行，返回 {表头: 值}；没有返回 None"""
        code = str(package_code).strip()
        for row in self.get_table_rows():
            if str(row.get("薪资包ID", "")).strip() == code:
                return row
        return None

    def get_total_text(self):
        """分页统计文本，如 '第 1-1 条/总共 1 条'；没有分页时返回空串"""
        try:
            return self.get_text("pagination_total", timeout=2000)
        except Exception:                        # noqa: BLE001
            return ""

    def get_empty_text(self):
        """空数据提示文本（通常是 '暂无数据'）；不存在时返回空串"""
        try:
            return self.get_text("table_empty", timeout=2000)
        except Exception:                        # noqa: BLE001
            return ""

    def assert_empty(self):
        """断言列表为空"""
        rows = self.get_table_rows()
        if rows:
            raise AssertionError(f"期望列表为空，实际有 {len(rows)} 行：{rows[:2]}")
        empty = self.get_empty_text()
        if "暂无数据" not in empty:
            raise AssertionError(f"期望出现「暂无数据」，实际空状态文本：{empty!r}")
        return True

    def assert_package_row(self, package_code, **expect):
        """断言某行字段（键用页面表头名：状态 / 国家/地区 / 供应商名称 / 员工人数 ...）"""
        row = self.get_row_by_code(package_code)
        if row is None:
            raise AssertionError(f"列表里没有薪资包 {package_code}，当前行：{self.get_table_rows()[:3]}")
        for key, value in expect.items():
            actual = str(row.get(key, ""))
            if str(value) not in actual:
                raise AssertionError(f"薪资包 {package_code} 的「{key}」期望包含 {value!r}，实际 {actual!r}")
        return row
