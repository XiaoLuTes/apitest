# autotest —— 接口 + UI 自动化统一框架

把原先两个独立框架合并成一个仓库、一套配置、一个执行入口：

| 用例集 | 目录 | 驱动方式 | 用例数据 |
| --- | --- | --- | --- |
| 接口自动化 `api` | `api/` | Excel 驱动（pytest paramtrize） | `api/testcase/*.xlsx` |
| UI 自动化 `ui` | `ui/` | YAML 驱动（Playwright） | `ui/testcases/**/*.yaml` |

两个用例集共用：`.env` 配置、日志实现（`core/logger.py`）、报告目录（`reports/`）、Allure 结果（`reports/allure-results`）、pytest 根配置与执行入口。

```
autotest/
├─ run.py                # 统一执行入口（api / ui / all）
├─ conftest.py           # pytest 根配置（路径、目录、用例集校验）
├─ pytest.ini            # 两个用例集共用的 pytest 配置
├─ .env / .env.example   # 统一配置（数据库、账号、Webhook、项目默认值）
├─ core/                 # 公共层
│   ├─ paths.py          # 统一路径（全部绝对化，任意工作目录可执行）
│   ├─ env.py            # 统一 .env 加载
│   └─ logger.py         # 统一日志工厂（API_/UI_ 前缀，输出到 reports/logs）
├─ api/                  # 接口用例集（原 api 框架）
│   ├─ common/           # 请求、断言、变量、Excel、数据库、重试、薪资包工具
│   ├─ config/setting.py
│   ├─ testcase/         # 用例 Excel
│   ├─ variable/         # 全局变量 + extract 临时变量
│   ├─ conftest.py       # 会话级夹具（结果文件、Allure、企微通知、DB 关闭）
│   └─ test_file.py      # Excel 用例入口
├─ ui/                   # UI 用例集（原 ui_playwright 框架）
│   ├─ config/           # settings.py + locators/
│   ├─ pages/            # 页面对象（base_page / gsr_admin_page / scan_login_page）
│   ├─ utils/            # 浏览器、执行器、元素定位、YAML、变量、企业微信
│   ├─ testcases/        # YAML 用例 + 附件
│   ├─ conftest.py       # browser 会话级夹具
│   └─ test_from_yaml.py # YAML 用例入口
└─ reports/              # 统一产物（不进 git）
    ├─ logs/ logs_error/ # API_log_*.log / UI_log_*.log
    ├─ results/api|ui/   # 执行结果文件（Excel 副本 / YAML 结果）
    ├─ downloads/        # 接口下载文件 + UI 浏览器下载
    ├─ screenshots/      # UI 失败截图
    ├─ auth/             # 企业微信扫码登录态（cookie 复用）
    └─ allure-results/   # allure 原始结果
```

## 1. 环境准备

```powershell
pip install -r requirements.txt
# UI 用例集首次使用还需要安装浏览器驱动
python -m playwright install chromium
```

配置：复制 `.env.example` 为 `.env`，填写数据库、账号、企业微信 Webhook、默认项目名。
优先级：系统环境变量 > `.env` > 代码默认值。

## 2. 执行用例

```powershell
python run.py --list                              # 查看所有用例集与项目名
python run.py api 薪资包结算                        # 跑接口用例
python run.py ui 薪资结算包收款包链路                 # 跑 UI 用例
python run.py all                                 # 两个用例集各跑 .env 里的默认项目
```

常用附加参数：

```powershell
python run.py api 审批流员工标签 -k 标签              # 只跑名称匹配的用例
python run.py api 薪资包结算 --report                # 跑完生成 allure html
python run.py ui 薪资结算包收款包链路 --headless       # 无头模式（二维码推送到企微）
```

也可以直接用 pytest（需先指定用例集，否则按 `all` 处理）：

```powershell
$env:TEST_SUITE="api"; $env:API_PROJECT="薪资包结算"; python -m pytest api -k file35
```

## 3. 两个用例集的约定差异

| 项 | 接口用例集 | UI 用例集 |
| --- | --- | --- |
| 项目名变量 | `API_PROJECT`（命令行优先） | `UI_PROJECT`（命令行优先） |
| 用例文件位置 | `api/config/setting.py` 的 `TEST_FLIELOADS` | `ui/config/settings.py` 的 `PROJECT_CONFIGS` |
| 执行结果 | `reports/results/api/*.xlsx`（源用例副本 + result 列） | `reports/results/ui/*.yaml` |
| 失败证据 | Allure 附件（请求/响应/断言） | `reports/screenshots/*.png` + Allure |

新增用例集项目：
- 接口：把 Excel 放到 `api/testcase/`，在 `TEST_FLIELOADS` 里加一行 `"项目名": "testcase/xxx.xlsx"`；
- UI：把 YAML 放到 `ui/testcases/`，在 `PROJECT_CONFIGS` 里加一项（页面对象、定位器、用例路径）。

## 4. 详细文档

两个用例集的完整写法说明保留在各自目录下：

- 接口用例集：`api/README.md`（Excel 列定义、动作表、断言、变量、薪资包相关动作等）
- UI 用例集：`ui/README.md`（YAML 步骤、动作、元素定位、扫码登录等）

## 5. 说明

- 原有独立框架（`D:\lu\pycharm\api`、`D:\lu\pycharm\ui_playwright`）保持原样，可继续单独使用；本仓库是合并后的新框架。
- 所有路径都基于 `core/paths.py` 计算成绝对路径，因此在 PyCharm 里直接运行某个测试文件、或在任意目录执行 `python D:\lu\pycharm\autotest\run.py api ...` 都能正确定位用例与报告。
