import openpyxl
from common.logger import logger


class Excel:
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

                # 读取表头（第一行）
                title = [sheet_obj.cell(row=1, column=col).value for col in range(1, max_col + 1)]
                # 读取用例数据（从第二行开始）
                for row in range(2, max_row + 1):
                    row_data = [sheet_obj.cell(row=row, column=col).value for col in range(1, max_col + 1)]
                    case_dict = dict(zip(title, row_data))
                    case_dict["sheet"] = sheet  # 标记用例所属Sheet
                    case_dict["row_num"] = row  # 标记用例所在行号，用于后续写入结果
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

    @staticmethod
    def excel_write(filename, sheet, row, column, result):
        """向Excel指定位置写入结果"""
        logger.info(f"写入Excel结果，文件：{filename}，Sheet：{sheet}，位置：行{row}列{column}，结果：{result}")
        wb = None
        try:
            wb = openpyxl.load_workbook(filename)
            # 定位目标Sheet
            if sheet not in wb.sheetnames:
                raise ValueError(f"Excel中未找到Sheet[{sheet}]，现有Sheet：{wb.sheetnames}")

            sheet_obj = wb[sheet]
            sheet_obj.cell(row=row, column=column).value = result  # 写入结果
            wb.save(filename)
            logger.info(f"Excel结果写入成功")
        except Exception as e:
            logger.error(f"写入Excel结果失败，错误信息：{str(e)}", exc_info=True)
            raise
        finally:
            if wb:
                wb.close()
                logger.info("Excel写入完成，文件已释放")
