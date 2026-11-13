import re

import yaml
from ui.utils.logger import logger

def read_yaml(file_path):
    # 读取yaml用例文件并解析（变量替换统一由 VariableStore.render 在执行时完成）
    with open(file_path, mode='r', encoding="utf-8") as a:
        value = yaml.load(stream=a, Loader=yaml.FullLoader)
        return value

def write_yaml(file_path, data):
    # 写入全局变量(替换掉原有)
    with open(file_path, 'w', encoding='utf-8') as file:
        yaml.dump(data, file, allow_unicode=True, sort_keys=False)

# =================== 统一变量存储与替换 ===================
class VariableStore:
    """统一变量存储：存值 + 渲染替换（统一 {变量名} 语法）
    用途：
      - 运行前 preload(settings)：把 username/password/customer/owner/replace_num 预置为变量
      - 执行中 set_variable()：save_text/save_value 动作把元素值存为变量
      - 执行中 get_variable(): 获取变量值-预留方法
      - 执行中 render()：把用例里 {变量名} 替换为变量值（兼容旧写法 {username} 等）
    """

    _vars = {}   # 类变量：进程内存，所有实例共享，pytest 进程结束自动清空

    @classmethod
    def set_variable(cls, name, value):
        """保存变量；若已存在同名变量，记录警告（提示可能重复定义），仍然覆盖"""
        if name in cls._vars:
            logger.warning(f"变量 [{name}] 已存在，将被覆盖: 旧值'{cls._vars[name]}' -> 新值'{value}'")
        cls._vars[name] = str(value)

    @classmethod
    def get_variable(cls, name, default=''):
        """读取变量；不存在时返回 default（默认空串），不抛异常"""
        return cls._vars.get(name, default)

    @classmethod
    def preload(cls, settings):
        """运行前预置：把 settings 里的常用配置导入为变量（conftest启动时调用一次）"""
        cls.set_variable("username", settings.LOGIN_USER)
        cls.set_variable("password", settings.PASSWORD)
        cls.set_variable("customer", settings.CUSTOMER)
        cls.set_variable("owner", settings.OWNER)
        cls.set_variable("replace_num", str(settings.TIME_STAMP))

    @classmethod
    def render(cls, text):
        """统一替换：把字符串中的 {变量名} 替换为变量值（变量不存在则替换为空串）

        转义：写 {{变量名}} 会原样输出 {变量名}（用来输"页面本身要的大括号占位符"，
        例如招聘平台的邮件模板占位符 {candidateName}，避免被当成框架变量替换掉）
        """
        if not isinstance(text, str):
            return text
        literals = []

        def _keep(match):
            literals.append("{" + match.group(1) + "}")
            return f"\x00{len(literals) - 1}\x00"

        text = re.sub(r"\{\{([A-Za-z_][A-Za-z0-9_]*)\}\}", _keep, text)
        for key, value in cls._vars.items():
            text = text.replace(f'{{{key}}}', value)
        for index, literal in enumerate(literals):
            text = text.replace(f"\x00{index}\x00", literal)
        return text

    @classmethod
    def dump(cls, mask_fields=('password',)):  # 打印变量快照时，替换字段
        """测试结束时打印所有变量，敏感字段打码（默认打码 password）"""
        logger.info("========== 本次运行变量快照 ==========")
        for name, value in cls._vars.items():
            if name in mask_fields:
                logger.info(f"{name} = ******")  # 敏感字段打码
            else:
                logger.info(f"{name} = {value}")
        logger.info("======================================")
