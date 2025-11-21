import yaml
extractfile = r"D:\python\2022-12\2023-1\extract.yaml"
# 提取变量文件路径
yaml_load = r"D:\python\2022-12\2023-1/"
# yaml用例文件路径
all_yaml = r"D:\python\2022-12\2023-1\all.yaml"
# 全局变量文件路径
def write_yaml(data):
    # 写入全局变量
    with open(extractfile, mode='a', encoding='utf-8') as a:
        yaml.dump(data=data, stream=a, allow_unicode=True)

def read_yaml(key):
    # 读取全局变量
    with open(extractfile, mode='r', encoding="utf-8") as a:
        value = yaml.load(stream=a, Loader=yaml.FullLoader)
        return value[key]

def clean_yaml():
    # 清空全局变量
    with open(extractfile, mode='w', encoding="utf-8") as a:
        a.truncate()

def read_all_yaml(key):
    # 根据key读取全局参数
    with open(all_yaml, mode='r', encoding='utf-8') as a:
        value = yaml.load(stream=a, Loader=yaml.FullLoader)
        return value[key]

def write_yaml_yl(yaml_file, data):
    # 写入用例yaml,a是追加写入
    with open(yaml_load + yaml_file, mode='a', encoding='utf-8') as b:
        yaml.dump(data=data, stream=b, allow_unicode=True)

def read_yaml_all():
    # 读取所有全局参数
    with open(all_yaml, mode='r', encoding='utf-8') as a:
        value = yaml.load(stream=a, Loader=yaml.FullLoader)
        return value

def read_yl_yaml(yaml_file, part):
    # 读取用例
    with open(yaml_load + yaml_file, mode='r', encoding='utf-8') as b:
        value = yaml.load(stream=b, Loader=yaml.FullLoader)
        new_value = value[part]
        return new_value

# def read_excel_yl_yaml(yaml_file):
#     # 读取用例
#     with open(r"D:\python\2022-12\2023-1/" + yaml_file, mode='r', encoding='utf-8') as b:
#         value = yaml.load(stream=b, Loader=yaml.FullLoader)
#         return value
#
# def update_yl_yaml(yaml_file, key, value):
#     # 更新yaml用例
#     old_data = read_excel_yl_yaml(yaml_file)
#     # 读取文件数据
#     old_data[key] = value
#     # 修改读取的数据（k存在就修改对应值，k不存在就新增一组键值对）
#     with open(r"D:\python\2022-12\2023-1/" + yaml_file, mode="w", encoding="utf-8") as f:
#         yaml.dump(old_data, f)
# def clean_yaml_yl(yaml_file):
#     # 清空全局变量
#     with open(r"D:\python\2022-12\2023-1/" + yaml_file, mode='w', encoding="utf-8") as b:
#         b.truncate()
