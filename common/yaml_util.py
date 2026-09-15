import yaml
from config.setting import setting


extractfile = setting.EXTRACTFILE
# 提取变量文件路径
yaml_load = setting.TEST_FLIELOAD_YAML
# yaml用例文件路径
all_yaml = setting.ALL_YAML
# 全局变量文件路径


class YamlVariableError(Exception):
    """变量文件读取异常（文件为空、格式异常、变量不存在）"""
    pass


def write_yaml(data):
    # 写入全局变量
    with open(extractfile, mode='a', encoding='utf-8') as a:
        yaml.dump(data=data, stream=a, allow_unicode=True)


def read_yaml(key):
    # 读取全局变量
    with open(extractfile, mode='r', encoding="utf-8") as a:
        value = yaml.load(stream=a, Loader=yaml.FullLoader)
    # 修复：变量文件为空/格式异常时，原先直接 value[key] 会抛 TypeError，
    # 被上层宽泛捕获后表现为"变量莫名没被替换"，排查成本很高，这里改为抛出明确异常
    if not isinstance(value, dict):
        raise YamlVariableError(f"变量文件为空或格式异常：{extractfile}")
    if key not in value:
        raise YamlVariableError(f"变量文件 {extractfile} 中不存在变量：{key}")
    return value[key]


def clean_yaml():
    # 清空全局变量
    with open(extractfile, mode='w', encoding="utf-8") as a:
        a.truncate()


# def write_yaml_yl(yaml_file, data):
#     # 写入用例yaml,a是追加写入
#     with open(yaml_load + yaml_file, mode='a', encoding='utf-8') as b:
#         yaml.dump(data=data, stream=b, allow_unicode=True)

def read_yaml_all():
    # 读取所有全局参数
    with open(all_yaml, mode='r', encoding='utf-8') as a:
        value = yaml.load(stream=a, Loader=yaml.FullLoader)
        return value

# def read_yl_yaml(yaml_file, part):
#     # 读取yaml用例
#     with open(yaml_load + yaml_file, mode='r', encoding='utf-8') as b:
#         value = yaml.load(stream=b, Loader=yaml.FullLoader)
#         new_value = value[part]
#         return new_value
