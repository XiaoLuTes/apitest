1、excel用例需要以json格式入参、yaml用例需要以键值对的格式入参、可参考现有文件
   excel文件code_id不能为空且必须从1开始
2、extract：提取返回作为全局变量 格式：{key：value(支持json提取、正则提取，建议json提取)}
   引用格式：${cloudID}
3、validata：断言  格式：{"$.result.resultCode": 0} （json格式的键值对）
4、需要修改路径的文件：
    yaml_util内的提取变量文件路径、yaml用例文件路径、全局变量文件路径
    pytest_ini文件内的allure报告采集地址
    pytest_ini文件内的testpath测试路径
    test_file文件内的pytest装饰器指定的yaml用例文件位置
    test_file文件内的pytest装饰器指定的excel用例文件位置
5、执行用例直接使用run文件
6、allure测试报告：使用浏览器打开位于reports文件夹内的index.html文件
7、全局参数写入all.yaml文件
    引用格式${cloudID}



api/
├── common/                   # 公共类
│   ├── database.py           # 数据库管理
│   ├── excel_read.yaml       # excel文件处理器
│   ├── executor.py           # 测试执行器
│   ├── logger.py             # 日志管理
│   ├── request_util.py       # 请求封装
│   ├── variable_handle.py    # 变量处理器
│   └── yaml_utils.py         # yaml文件处理器
│
├── config/                   # 配置文件
│   ├── _init_.py
│   └── setting.py            # 全局配置文件
│
├── reports/                  # 测试报告
│   ├── logs                  # info级日志文件
│   ├── logs_error            # error级日志文件
│   └── temp                  # allure测试报告引用文件
│
├── testcases/                # 测试用例文件夹
│   ├── test_approval.xlsx    # 测试用例文件-假勤项目
│   ├── test_test.xlsx        # 测试用例文件-调试框架用
│   └── test_yl.yaml          # 测试用例文件-yaml格式
│
├── variable/                 # 变量管理类
│   ├── all.yaml              # 全局变量-测试环境
│   ├── all_prepro.yaml       # 全局变量文件-预生产环境
│   ├── all_pro.yaml          # 全局变量文件-生产环境
│   └── extract.yaml          # 临时变量
│
├── conftest.py               # pytest fixture配置
├── pytest.ini                # pytest配置文件
├── readme.txt                # 框架说明
├── requirements.txt          # 依赖库
├── run.py                    # run文件(Jenkins执行/本地调试用)
└── test_fire.py              # 测试执行文件(依赖这个文件串联各个类进行测试)
