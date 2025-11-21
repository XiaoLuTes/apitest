import logging
import os

logger = logging.getLogger('cloud')
# 定义log文件名
logger.setLevel(logging.DEBUG)
# 定义log打印级别
formatter = logging.Formatter("[%(asctime)s] [%(filename)s] [%(levelname)s] %(message)s")
# 定义日志的内容，时间、内容的级别、显示的内容


# # 控制台的输出处理器
# sh = logging.StreamHandler()
# sh.setFormatter(formatter)
# # 设置日志级别
# sh.setLevel(logging.DEBUG)
# # 添加控制台的输出
# logger.addHandler(sh)
# 放在日志文件里面
logs = os.path.join(os.path.dirname(__file__), './logs')
# 如果目录下没有logs文件夹，就创建一个logs
if not os.path.exists(logs):
    os.mkdir(logs)
logfile = os.path.join(logs, 'cloud.log')
fh = logging.FileHandler(logfile, encoding='utf-8', mode='a')
fh.setFormatter(formatter)
fh.setLevel(logging.DEBUG)
logger.addHandler(fh)
