# UI 自动化测试框架

基于 **Playwright + Pytest + YAML 数据驱动** 的 Web UI 自动化测试框架，支持多项目切换、OCR 验证码自动登录、运行时变量、数据库校验、失败截图与日志留证。

---

## 一、技术栈

| 组件 | 说明 |
|---|---|
| Playwright | 浏览器自动化（Chromium，sync API）|
| Pytest | 测试框架（参数化驱动用例）|
| PyYAML | 用例与定位器配置 |
| ddddocr / OpenCV | 验证码 OCR 识别 |
| PyMySQL | 数据库校验 |
| python-dotenv | 本地凭据读取（.env）|
| openpyxl | Excel 填写（edit_excel 动作）|
| Allure | 测试报告（可选）|

## 二、目录结构

```
ui_playwright/
├── run.py                  # 入口脚本（pytest.main）
├── test_from_yaml.py       # pytest 测试类（参数化加载用例）
├── conftest.py             # pytest fixtures + VariableStore.preload(settings) 启动预置
├── pytest.ini              # pytest 配置
├── requirements.txt        # 依赖清单
├── .env                    # 本地凭据（已被 .gitignore 排除，勿提交）
├── .env.example            # 凭据模板（可提交）
├── .gitignore
├── README.md               # 本文档
├── 超时配置说明.md          # 超时配置速查
│
├── config/
│   ├── settings.py         # 全局配置（环境/凭据/项目/超时/路径）
│   └── locators/           # 元素定位器（按页面分文件）
│       ├── gsr_admin_page.yaml               # 登录页元素（gsr_admin_page 分组）
│       ├── gsr_admin_page_management.yaml    # 管理平台元素（gsr_admin_page_management 分组）
│       ├── new_position_element_locators.yaml
│       └── pt_new_position_v2.yaml
│
├── pages/                  # 页面对象层
│   ├── base_page.py        # 操作基类（查找/点击/输入/上传/下载/Excel填写/等待/截图/加载动画检测）
│   ├── gsr_admin_page.py   # 管理端页面对象（OCR 自动登录 + 进入管理端）
│
├── utils/                  # 工具层
│   ├── executor.py         # 动作执行器（YAML 动作 → 页面方法，含 save_* 动作）
│   ├── yaml_load.py        # 用例加载 + 结果写入 reports/test_results
│   ├── page_manager.py     # 页面注册与导航
│   ├── element_locator.py  # 定位器读取（YAML → 分组字典）
│   ├── browser.py          # 浏览器引擎（单例）
│   ├── captcha_ocr.py      # 验证码 OCR（连通域分割 + 多级回退）
│   ├── database.py         # 数据库操作
│   ├── common.py           # 通用工具（read_yaml/write_yaml + VariableStore 变量存储）
│   └── logger.py           # 日志（按天切割 + 7天自动清理）
│
├── testcases/              # 测试用例（YAML）
│   ├── eor_salary_ettlement/   # 薪资结算包收款包链路（当前在用）
│   ├── pt_new_position/        # 招聘平台（旧版）
│   ├── pt_new_position_v2/     # 招聘平台（维护版）
│   ├── pt_new_preparation/     # 招聘准备
│   └── template.yaml           # 用例模板
│
└── reports/                # 产物目录（.gitignore 排除）
    ├── logs/               # 运行日志（按天）
    ├── logs_error/         # 错误日志（按天）
    ├── screenshots/        # 失败截图
    ├── temp/               # Allure 临时文件
    ├── downloads/          # 下载的文件（下载→编辑→上传 中间产物）
    └── test_results/       # 测试结果（每次运行汇总 1 个 YAML，用例源文件只读）
```

## 三、环境准备

```bash
# 1. 安装依赖（国内可用阿里云镜像）
pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/

# 2. 安装 Playwright 浏览器（首次）
set PLAYWRIGHT_BROWSERS_PATH=C:\playwright-browsers
playwright install chromium
```

### 3.1 凭据配置（.env 或环境变量）

敏感配置**不写在代码里**，通过 `.env`（本地）或环境变量（Jenkins）提供：

```bash
# 复制模板 → 填写真实值
copy .env.example .env
```

```env
# .env（已被 .gitignore 排除）
LOGIN_USER=你的登录账号
PASSWORD=你的登录密码
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=你的数据库用户
DB_PASSWORD=你的数据库密码
DB_NAME=你的数据库名
```

**优先级**：Jenkins/系统环境变量 > `.env` > settings 默认值（敏感项默认已清空）

⚠️ **Windows 注意**：不要用 `USERNAME` 作为自定义键名（系统保留变量，会被 Windows 用户名遮蔽），框架使用 `LOGIN_USER`。

## 四、配置说明（config/settings.py）

### 4.1 多项目切换

```bash
# 方式一：改 settings.py 的 CURRENT_PROJECT
# 方式二：环境变量覆盖（Jenkins 推荐）
$env:CURRENT_PROJECT = "薪资结算包收款包链路"
python run.py
```

每个项目在 `PROJECT_CONFIGS` 中配置：PAGE_NAME / ELEMENT_LOCATORS / TESTCASES_PATH / LOADING_SELECTOR（可选）。

### 4.2 超时配置（详见 `超时配置说明.md`）

| 配置 | 默认值 | 单位 | 用途 |
|---|---|---|---|
| `IMPLICIT_WAIT` | 15000 | 毫秒 | page 全局默认超时（元素操作兜底）|
| `EXPLICIT_WAIT` | 30 | 秒 | 等待元素值变化总超时 |
| `TIME_FIND` | 3000 | 毫秒 | 轮询单次查找超时 |
| `REFRESH_INTERVAL` | 5 | 秒 | wait_text/value 刷新间隔 |
| `REFRESH_TIME` | 15 | 秒 | wait_exists 刷新间隔 |
| `WAIT_ELEMENT_APPEAR` | 120 | 秒 | 元素出现总超时 |
| `DB_TIMEOUT` | 20 | 秒 | 数据库连接超时 |
| `SLOW_MO` | 500 | 毫秒 | 操作延迟（调试用，Jenkins 应设 0）|

### 4.3 加载动画配置（按项目）

项目进入时有加载动画（如 `#loader-wrapper`），在**该项目配置段**加：

```python
"薪资结算包收款包链路": {
    ...
    "LOADING_SELECTOR": "#loader-wrapper",   # CSS 选择器，多个逗号分隔
}
```

未配置的项目**不启用**加载动画检测（框架默认零影响）。点击/登录时会自动等待动画消失。

## 五、编写测试用例

### 5.1 用例格式

```yaml
test_cases:
  - id: 薪资结算包-1
    name: 创建EOR薪资结算包
    steps:
      - step_name: 输入账号
        element: username_input
        action: input
        data: '{username}'        # 占位符必须加引号！（不加会被 YAML 解析成 dict）
      - step_name: 保存结算包code
        element: settlement_package_code
        action: save_text         # 保存为变量
        data: package_code        # 变量名（不带 {}）
      - step_name: 引用变量
        element: search_input
        action: input
        data: '{package_code}'    # 执行时替换为保存的值
```

### 5.2 动作列表

| 动作 | 必填 | 说明 |
|---|---|---|
| `input` | element/action/data | 输入文本（`expected: true` 可校验输入结果）|
| `click` | element/action | 点击（真实点击重试 + 加载动画检测，无 JS 强点）|
| `check_text` | element/action/data | 校验元素文本包含 data |
| `check_value` | element/action/data | 校验表单元素值包含 data |
| `check_exists` | element/action/data | 校验元素存在与否（data: 存在/不存在）|
| `wait_exists` | element/action | 等待元素出现（最长120s，每15s刷新）|
| `wait_text` / `wait_value` | element/action/data | 等待文本/值变为 data（最长30s，每5s刷新）|
| `save_text` / `save_value` | element/action/data | 取元素文本/值存入运行时变量（自动等待非空）|
| `upload` | element/action/data | 上传文件（data 为文件路径或变量）|
| `download` | element/action/data | 触发浏览器下载，保存到 reports/downloads（data=保存文件名，存同名变量）|
| `edit_excel` | action/data/expected | 填写 Excel 单元格（data=文件路径, expected=填写配置JSON），覆盖保存原文件 |
| `wait` | action/data | 固定等待（data 为秒）|
| `up` / `down` / `enter` | element/action | 键盘操作 |
| `sql` / `sql_update` | action/data/expected | 数据库查询/更新校验 |
| `screenshot` | action | 主动截图 |

### 5.3 变量机制

| 类型 | 写法 | 来源 | 替换时机 |
|---|---|---|---|
| 预置变量 | `{username}` `{password}` `{customer}` `{owner}` `{replace_num}` | conftest 启动时从 settings 预置 | 执行步骤时 |
| 运行时变量 | `{任意变量名}` | save_text/save_value 保存 | 执行步骤时 |

- **占位符必须加引号**：`data: '{变量名}'`（不加引号 YAML 解析成 dict，不会替换）
- 替换发生在 `execute_step` 开头（data/expected 字段），字符串任意位置/多次出现均可
- 同一次运行内全局共享（跨用例可用），进程结束自动清空

### 5.4 定位器格式（config/locators/*.yaml）

```yaml
gsr_admin_page:                 # 页面分组（与页面注册名对应）
  username_input:
    by: id                      # id / xpath / css / name
    value: username
  hidden_upload:                # 隐藏元素：名称加 hidden_ 前缀
    by: xpath
    value: //input[@type='file']
```

⚠️ **多文件定位器**：若登录元素与管理平台元素分属不同 YAML，需在项目 `ELEMENT_LOCATORS` 配置中指向**包含对应分组的文件**（当前支持单文件，含全部所需分组的 YAML）。

### 5.5 文件操作（下载 → 编辑 → 上传）

```yaml
- step_name: 1、下载导入模板
  element: download_button        # 触发下载的元素
  action: download
  data: import_template.xlsx      # 保存文件名（同时作为变量名）

- step_name: 2、填写导入模板
  action: edit_excel              # 不需要 element
  data: '{import_template.xlsx}'  # 文件路径（变量引用）
  expected: '{"A1": "张三", "B2": "20260903", "C3": "{staff_id_first}"}'  # 填写配置JSON（变量可嵌入）

- step_name: 3、上传填写好的文件
  element: upload_input
  action: upload
  data: '{import_template.xlsx}'  # 覆盖保存过，内容已是填写后的
```

说明：
- 下载文件保存到 `reports/downloads/`（基于项目根，不依赖启动目录）
- `edit_excel` **覆盖保存原文件** → 变量路径不变，upload 引用同一变量即为填写后的文件
- `expected` 中的 `{变量名}` 同样会被替换（render 只替换真实存在的变量，`{"A1": ...}` 等 JSON 结构不会被误替换）

## 六、运行测试

```bash
# 本地
python run.py

# 指定项目（环境变量）
$env:CURRENT_PROJECT = "薪资结算包收款包链路"
python run.py

# pytest 直跑 / 按关键字筛选
python -m pytest -v -k "创建EOR"
```

**Jenkins 建议**：环境变量注入 `CURRENT_PROJECT`、凭据（LOGIN_USER/PASSWORD/DB_*）、`SLOW_MO=0`；`PLAYWRIGHT_BROWSERS_PATH` 固定浏览器缓存目录。

## 七、测试结果与报告

| 产物 | 位置 | 说明 |
|---|---|---|
| 结果汇总 | `reports/test_results/<项目>_<批次>.yaml` | 每次运行 1 个文件，含全部用例 id/name/result |
| 失败截图 | `reports/screenshots/` | 自动截图留证 |
| 运行日志 | `reports/logs/UI_log_日期.log` | 按天切割，7 天自动清理（保留最新一份）|
| 错误日志 | `reports/logs_error/UI_error_log_日期.log` | 同上 |

**用例源文件只读**：结果写往 reports/test_results，不污染 testcases YAML。

## 八、框架能力

1. **自动登录**：`perform_login` OCR 识别验证码 + 自动重试；登录后自动进入管理平台（无缓存走 /sys 选择页），等待页面加载动画结束（`_wait_if_loading`）
2. **首页点击防遮挡**：真实点击（无 JS 强点）；页面基础配置，进入后检测加载动画（按项目 `LOADING_SELECTOR` 配置，无动画零开销）；点击失败自动重试（存在性检查 + expect 可点击等待）
3. **异步取值**：`get_text`/`get_element_value` 空值自动重试（元素不存在直接抛错）
4. **轮询静默**：wait 类方法轮询不产生 Allure 噪音步骤
5. **运行时变量**：save 动作 + `{变量名}` 引用，解耦用例间数据依赖
6. **文件下载与 Excel 填写**：download 动作捕获浏览器下载到 reports/downloads；edit_excel 用 openpyxl 填写单元格（覆盖保存），上传直接引用变量路径

## 九、注意事项

1. **占位符必须加引号**：`data: '{xxx}'`——漏引号会被 YAML 解析成 dict，替换失效（报错文案会出现 `{'xxx': None}`）
2. **wait_text/wait_value 会刷新页面**：请勿在"填写表单中途"使用
3. **用例间避免隐式依赖**：推荐用 save 变量传递数据，不要依赖前序用例留下的页面状态
4. **凭据安全**：.env 已被 .gitignore 排除；旧版本 settings.py 明文密码若已进 git 历史，建议更换测试环境密码
5. **SLOW_MO**：本地调试可设 100~500（慢速观察），Jenkins 务必设 `SLOW_MO=0`（每个 Playwright 操作间会插入该延迟）

## 十、常见问题

**Q: 元素查找超时？**
A: 多为环境响应慢或定位器失效；调大 `IMPLICIT_WAIT` 或检查定位器。注意 get_text/get_element_value 对"元素不存在"是直接抛错（不做空值重试）。

**Q: 登录失败/验证码识别失败？**
A: 确认环境可用 + 缓存场景（/sys vs /statistics 都视为登录成功）；截图在 reports/screenshots。

**Q: 步骤报"预期包含 '{'xxx': None}'"？**
A: 用例里占位符没加引号，被 YAML 解析成 dict——改为 `data: '{xxx}'`。

**Q: 结果文件部分用例 result 为空？**
A: 用例因环境问题中断未执行；重跑即可（同一批次文件累积写入）。
