import os
import shutil
import time

import openpyxl

from config.setting import setting
from common import run_state
from common.logger import logger


class Excel:
    # 用例执行结果缓存：[(文件名, sheet, 行, 列, 结果), ...]
    # 修复：原先每执行一条用例就 load_workbook + save 一次源用例文件，
    # 用例多时极慢，且文件被 Excel 打开或并发执行时会写失败、互相覆盖。
    # 现在改为先缓存，会话结束时由 save_results() 一次性写入结果文件（不改动源用例文件）。
    _pending_results = []

    @staticmethod
    def read_excel(fileload):
        """读取Excel所有Sheet的测试用例，转换为字典列表"""
        logger.info(f"开始读取测试用例，文件路径：{fileload}")
        all_data = []  # 存储所有Sheet的用例
        wb = None
        try:
            wb = openpyxl.load_workbook(fileload)
            sheet_names = wb.sheetnames
            logger.info(f"检测到Excel包含Sheet：{sheet_names}")

            for sheet in sheet_names:
                sheet_obj = wb[sheet]  # 定位Sheet
                max_row = sheet_obj.max_row  # 记录最大行
                max_col = sheet_obj.max_column  # 记录最大列
                logger.info(f"处理Sheet[{sheet}]，总行数：{max_row}，总列数：{max_col}")
                if max_col < 9:  # 无有效用例（仅表头）
                    logger.warning(f"Sheet[{sheet}]无有效测试用例（仅表头），跳过")
                    continue
                title = [sheet_obj.cell(row=1, column=col).value for col in range(1, max_col + 1)]

                # 定位结果列（默认第7列），避免回写结果时硬编码列号
                result_col = 7
                for col, header in enumerate(title, start=1):
                    if isinstance(header, str) and header.strip().lower() == 'result':
                        result_col = col
                        break
                else:
                    logger.warning(f"Sheet[{sheet}]表头未找到result列，回写结果将默认使用第7列")

                # 读取用例数据（从第二行开始）
                for row in range(2, max_row + 1):
                    row_data = [sheet_obj.cell(row=row, column=col).value for col in range(1, max_col + 1)]
                    # 跳过空行（只保留格式没有内容的行），避免产生无效用例
                    if all(value is None or str(value).strip() == '' for value in row_data):
                        logger.info(f"Sheet[{sheet}]第{row}行为空行，跳过")
                        continue
                    case_dict = dict(zip(title, row_data))
                    case_dict["sheet"] = sheet  # 标记用例所属Sheet
                    case_dict["row_num"] = row  # 标记用例所在行号，用于后续写入结果
                    case_dict["result_col"] = result_col  # 标记结果列，用于后续写入结果
                    all_data.append(case_dict)

            logger.info(f"Excel用例读取完成，共获取{len(all_data)}条有效用例")
        except Exception as e:
            logger.error(f"读取Excel用例失败，错误信息：{str(e)}", exc_info=True)
            raise
        finally:
            # 关闭工作簿，释放文件资源
            if wb:
                wb.close()
                logger.info("Excel文件已释放")
        return all_data

    @classmethod
    def record_result(cls, filename, sheet, row, column, result):
        """缓存一条用例的执行结果（不立即写文件）"""
        cls._pending_results.append((filename, sheet, row, column, result))

    @classmethod
    def save_results(cls):
        """把缓存的执行结果写入“结果文件”
        结果文件 = 源用例文件的完整副本（所有 sheet、所有列原样保留）+ 本次执行的 result 列，
        输出到 setting.RESULT_PATH（如 reports/results/test_approval_20260915_143012.xlsx）。
        源用例文件只读，不再被修改。
        返回：本次实际生成的结果文件路径列表（供 allure 报告附加）。
        """
        if not cls._pending_results:
            logger.info("无待写入的用例执行结果")
            return []

        # 按源文件分组，并先清空缓存（避免写失败后重复写入）
        grouped = {}
        for filename, sheet, row, column, result in cls._pending_results:
            grouped.setdefault(filename, []).append((sheet, row, column, result))
        cls._pending_results.clear()

        # 结果目录不存在时自动创建；同一轮执行产生的多个结果文件共用同一个时间戳
        os.makedirs(setting.RESULT_PATH, exist_ok=True)
        stamp = time.strftime('%Y%m%d_%H%M%S')
        outcome = run_state.summary()  # 本次执行的通过 / 失败 / 跳过条数，写进结果文件名
        outcome_text = f"通过{outcome['passed']}_失败{outcome['failed']}_跳过{outcome['skipped']}"
        created = []  # 本次实际生成的结果文件，供 allure 报告附加

        for filename, items in grouped.items():
            stem = os.path.splitext(os.path.basename(filename))[0]
            target = os.path.join(setting.RESULT_PATH, f"{stem}_{stamp}_{outcome_text}.xlsx")
            wb = None
            try:
                # 先整体复制源文件，保证结果文件包含源文件的全部内容
                shutil.copy2(filename, target)
                wb = openpyxl.load_workbook(target)
                written = 0
                for sheet, row, column, result in items:
                    if sheet not in wb.sheetnames:
                        logger.warning(f"结果文件中未找到Sheet[{sheet}]，跳过该条结果写入")
                        continue
                    wb[sheet].cell(row=row, column=column).value = result
                    written += 1
                wb.save(target)
                logger.info(f"用例执行结果已写入结果文件：{target}（共{written}条）")
                created.append(target)
            except Exception as e:
                # 结果落盘属于附加动作，失败只记录错误，不影响用例本身的执行结论
                logger.error(f"用例执行结果写入失败，源文件：{filename}，目标文件：{target}，错误信息：{str(e)}", exc_info=True)
            finally:
                if wb:
                    wb.close()

        return created
