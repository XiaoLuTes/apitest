1、用例以excel文件或yaml文件放到test_cloud目录下面
    使用yaml用例的方法注释掉了，需要使用注释回来就可以，位置：test_file.py文件test_cloud方法
2、excel用例需要以json格式入参、yaml用例需要以键值对的格式入参、可参考现有文件
   excel文件code_id不能为空且必须从1开始、excel文件标题需与现有模板一致
3、extract：提取返回作为全局变量 格式：{key：value(支持json提取、正则提取，建议json提取)}
   引用格式：${cloudID}
4、validata：断言  格式：{"result.resultCode": 0} （json格式的键值对）
5、只封装了get和post方法
6、需要修改路径的文件：
    yaml_util内的提取变量文件路径、yaml用例文件路径、全局变量文件路径
    pytest_ini文件内的allure报告采集地址
    pytest_ini文件内的testpath测试路径
    test_file文件内的pytest装饰器指定的yaml用例文件位置
    test_file文件内的pytest装饰器指定的excel用例文件位置
7、执行用例直接使用run文件
8、allure测试报告：使用浏览器打开位于reports文件夹内的index.html文件
9、全局参数写入all.yaml文件
    引用格式${cloudID}
10、