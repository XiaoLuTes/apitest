import openpyxl

from common.logger import logger


class Excel:

    @staticmethod
    def excel_read(fireload):
        logger.info(f"测试用例路径：{fireload}")
        # sheet页面，row行，column列，cell格子
        file = openpyxl.load_workbook(fireload)
        sheet_names = file.sheetnames
        for sheet in sheet_names:
            sheet_row = file['' + sheet + '']
            max_row = sheet_row.max_row
            # 记录最大行
            max_column = sheet_row.max_column
            # 记录最大列
            datas = []
            for row in range(1, max_row + 1):
                data_list = []
                for column in range(1, max_column + 1):
                    data = sheet_row.cell(row=row, column=column).value
                    data_list.append(data)
                datas.append(data_list)
                # 通过定位sheet里的位置row，column提取cell内的值
                # 并写入data_list
            title = datas[0]
            last_data = []
            for value in datas[1:]:
                dict_data = dict(zip(title, value))
                last_data.append(dict_data)
                # 转换为字典形式
            return last_data

    @staticmethod
    def excel_write(filename, row, column, result):
        # 写入excel
        # data = Excel().excel_read(filename)
        file = openpyxl.load_workbook(filename)
        sheet_names = file.sheetnames
        for sheet in sheet_names:
            sheet2 = file['' + sheet + '']
            sheet2.cell(row=row, column=column).value = result
            file.save(filename)
