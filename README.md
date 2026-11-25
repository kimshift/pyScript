# pyScript —— 个人 Python 脚本集合

> 一个仓库放多个互不干扰的 Python 脚本：共享一套运行时与命令入口，各自独立的代码、依赖分组、配置和资源。
> 目前包含：**雷电模拟器（LDPlayer）批量自动化**、**WorkBuddy 积分签到**、**汽水音乐自动看广告**。

---

## 快速开始

```sh
mise install          # 按 mise.toml 装好 python 3.13 + uv
mise run setup        # 创建 .venv 并安装依赖（= uv sync --extra ld --extra ocr）
mise run ld:check     # 自检：加载依赖与配置，不做任何点击
```

### 交互式选任务：`npm start`

记不住 task 名时，直接 `npm start`：脚本会在终端按 `ld` / `qs` / `wb` 分组列出任务让你选。

```sh
npm start               # ↑/↓ 移动，Enter 执行，直接打字过滤，Esc 退出
npm start -- ld:check    # 不想进菜单：直接跑某个 task（等价 mise run ld:check）
npm start -- --list      # 只打印任务清单
npm start -- --config    # 打印菜单配置文件路径
```

菜单内容由 **`config/mise-menu.txt`** 决定（首次运行自动生成，把所有 task 收录进去）：

```txt
# [ld]
ld:backup      # 按 ID 范围备份模拟器
ld:check       # 自检：加载依赖与配置，不做任何鼠标点击
# ld:info      # ← 行首加 # 就不再出现在菜单里（记录仍保留）
```

- 想隐藏某个任务：在那一行行首加 `# `
- 想调整顺序：直接挪动行或整段的位置
- `mise.toml` 里新增的 task 会自动追加到配置文件末尾对应的分组；删掉该文件会重新生成
- 直接用 `npm start -- <task>` 执行不受隐藏影响，只要 `mise.toml` 里有这个 task 就能跑

> 实现见 `script/mise-menu.js`（只用 Node 内置模块，无需 `npm install`）。

> 环境由 [mise](https://mise.jdx.dev/) 管理（固定 Python 3.13），依赖由 [uv](https://docs.astral.sh/uv/) 管理（`pyproject.toml` + `uv.lock`）。
> 不再需要手动 `pip install`，也不再依赖系统里的全局 Python。

## 环境都装在哪（全部在 D 盘）

| 内容 | 位置 | 由谁决定 |
|---|---|---|
| mise 本体 | `D:\Program\mise\bin\mise.exe` | 安装时选择 |
| mise 安装的运行时（python / uv / node / pnpm） | `D:\Program\mise\installs\` | `MISE_DATA_DIR` |
| mise 下载缓存 | `D:\Program\mise\cache\` | `MISE_CACHE_DIR` |
| uv 包缓存（wheel/sdist） | `D:\Program\mise\cache\uv` | `UV_CACHE_DIR` |
| pip 包缓存 | `D:\Program\mise\cache\pip` | `PIP_CACHE_DIR` |
| 本项目虚拟环境 | `<仓库>\.venv` | 项目内 |
| 系统 Python / 用户级包 | ❌ 不使用 | — |

以上四个 `MISE_*` / `UV_*` / `PIP_*` 变量都是**用户级环境变量**，改完需要**重开终端或 IDE** 才生效（已打开的窗口继承的是旧环境）。

**双保险**：部分程序（如某些 IDE/助手）是由旧进程派生的，重启也拿不到新的环境变量。因此额外在 C 盘建立了三个**目录联接（junction）**，物理指向 D 盘：

| 联接路径 | 真实位置 |
|---|---|
| `%LOCALAPPDATA%\mise` | `D:\Program\mise` |
| `%LOCALAPPDATA%\uv` | `D:\Program\mise\cache\uv` |
| `%LOCALAPPDATA%\pip` | `D:\Program\mise\cache\pip` |

这样即便某个进程完全读不到环境变量、mise 退回默认目录，写进去的文件实际仍落在 D 盘（`sys.executable` 可能显示 C 盘路径，`os.path.realpath()` 会显示 D 盘真实路径）。

---

## 目录约定

```
pyScript/
├── pyproject.toml          依赖登记处：基础依赖 + 按脚本分组的 optional-dependencies
├── uv.lock                 锁定文件（必须提交）
├── mise.toml               运行时版本 + 所有命令入口（mise run <task>）
├── kit/                    跨脚本公共库：只放与业务无关的能力
│   ├── paths.py            仓库/脚本目录定位
│   ├── config.py           JSON 配置读写
│   └── log.py              统一日志
├── tools/                  一个子目录 = 一个脚本（只放代码与资源）
│   ├── ld_emulator/        雷电模拟器批量自动化
│   │   ├── __main__.py     入口：python -m tools.ld_emulator <动作>
│   │   ├── emulator.py     业务动作（create/start/backup/restore/...）
│   │   ├── common.py       键鼠 / 模板匹配 / 进程封装
│   │   ├── data.py         按钮名 → 图片文件名 映射
│   │   ├── backends/       外部接口封装：ldconsole.py（官方命令行）
│   │   ├── adapters/       可替换的底层库：screen(mss) / hotkey(pynput) / dialog(tkinter)
│   │   └── assets/image/   模板图片（common/ 与 emulator/）
│   └── wb_reward/          WorkBuddy 积分签到（计划任务驱动）
│       ├── __main__.py     入口：python -m tools.wb_reward <动作>
│       └── runner.py       调用 workbuddy-reward-helper，含重试/互斥/日志轮转
│   └── qishui_auto/        汽水音乐自动看广告（adb 截图 + OCR 点击）
│       ├── __main__.py     入口：python -m tools.qishui_auto <动作>
│       ├── runner.py       主循环：截图 → OCR → 决策 → 点击
│       ├── adb.py          adb 封装（截图 / 点击 / 分辨率 / 音量）
│       ├── ocr.py          RapidOCR 主通道
│       ├── uia.py          uiautomator 兜底通道（默认自动探测，多数设备不可用）
│       └── match.py        文字匹配与点击优先级（纯函数，可单测）
├── config/                 所有脚本的配置集中在这里（详见 config/README.md）
│   ├── README.md           新电脑怎么配（先看这个）
│   ├── ld_emulator.json    雷电自动化的公共配置
│   ├── wb_reward.json      积分签到的超时/重试/日志上限
│   ├── qishui.json         汽水看广告的目标文案 / ROI / 节奏
│   └── *.local.json        本机私有覆盖（gitignore 忽略，不入库）
├── logs/                   所有脚本的运行日志，按脚本名分子目录（不入库）
│   └── wb_reward/          scheduler.log（执行过程）+ result.log（结果摘要）
├── scripts/
│   ├── new_tool.py         新脚本脚手架
│   └── release.sh          推送到 gitee / github
├── tests/
│   └── legacy/             历史手工脚本（不参与 pytest）
├── docs/                   方案、规范与审查文档
├── script/                 Windows 双击用的 bat
└── cache.txt               生成物（gitignore 忽略）
```

---

## 新增一个脚本

```sh
python scripts/new_tool.py my_tool     # 生成 tools/my_tool/ 骨架
```

然后三步：

1. **登记依赖**：在 `pyproject.toml` 的 `[project.optional-dependencies]` 加分组（能复用已有组就别新建）：
   ```toml
   [project.optional-dependencies]
   mytool = ["requests>=2.32"]
   ```
2. **加命令入口**：在 `mise.toml` 里加 task：
   ```toml
   [tasks."my:run"]
   run = "uv run --extra mytool python -m tools.my_tool"
   ```
3. **运行**：`mise run my:run`，或临时 `uv run --extra mytool python -m tools.my_tool`。

详细规范见 [`docs/项目结构规范.md`](docs/项目结构规范.md)。

---

## 雷电模拟器自动化（tools/ld_emulator）

通过屏幕模板匹配（OpenCV）+ 鼠标模拟（pyautogui）操作 **雷电多开器**：批量创建/启动、批量设置分辨率与内存、批量安装 APK、开关同步、应用权限设置、备份/还原。

### 运行

| 命令 | 说明 |
|---|---|
| `mise run ld:create` | 批量创建 → 配置 → 启动 → 装包 → 同步 → 权限 → 关同步 |
| `mise run ld:start` | 启动所有已停止的模拟器 |
| `mise run ld:info` | 列出全部实例（index / 状态 / 分辨率 / 标题），**只读** |
| `mise run ld:create-txt` | 按配置生成 `cache.txt` |
| `mise run ld:backup` | 按 ID 范围备份 |
| `mise run ld:restore` | 按 ID 范围还原 |
| `mise run ld:quit-all` | 关闭全部模拟器 |
| `mise run ld:check` | 自检（只加载依赖与配置，不点击） |
| `mise run ld:gui` | 强制走旧的纯图像 GUI 流程（回滚用） |

等价的底层写法：`uv run --extra ld python -m tools.ld_emulator <动作> [--backend gui]`

### 两种后端（`config/ld_emulator.json` 的 `backend`）

| 后端 | 覆盖范围 | 说明 |
|---|---|---|
| `cli`（默认） | 11 个动作中的 10 个 | 走雷电官方 `ldconsole.exe`：新建、改分辨率/内存、启动、装包、备份/还原、排列窗口、关闭、查状态 |
| `gui` | 全部动作 | 重构前的图像匹配 + 点击，遇到问题可一键回滚 |

无论哪种后端，**同步器开关**和**模拟器内应用权限**都只能走 GUI（`ldconsole` 没有对应命令），所以 `pyautogui` 仍然保留，但调用范围已从 22 处收敛到兜底分支。

`npm run create_ld` / `serve_ld` / `create_txt` 仍可用（已改为转发到 mise）。Windows 双击：`script/创建雷电.bat`、`script/启动雷电.bat`。

### 配置（config/ld_emulator.json）

> **所有配置都在仓库根 `config/` 下**，新机器只需看这一个目录：见 [`config/README.md`](config/README.md)。
> **机器私有路径不写进公共配置。** `emulator_path` / `backup_path` / `emulator_install_path` 三项默认为空，
> 本机真实值请填进 `config/ld_emulator.local.json`（已 gitignore，不会被提交）。
> 新机器：`cp config/ld_emulator.local.example.json config/ld_emulator.local.json` 后按需修改；留空则走自动探测。

| 字段 | 说明 |
|---|---|
| `backend` | `cli`（默认，ldconsole 优先）/ `gui`（纯图像点击，回滚用） |
| `emulator_name_prefix` | 新建实例的名称前缀，默认 `雷电-`（编号拼在后面，如 `雷电-248`） |
| `emulator_resolution` | 新建/修改实例的分辨率 `宽,高,dpi`，如 `1080,1920,480`；留空则不修改 |
| `emulator_memory` | 实例内存 MB（256/512/1024/2048/4096）；`null` 表示不修改 |
| `emulator_path` | 雷电多开器可执行文件路径；**留空=自动探测**（`LDPLAYER_DIR` → PATH → 常见目录） |
| `emulator_process_name` | 进程名 |
| `emulator_end_id` | 创建起点（0=从 `雷电-1` 开始）。**运行进度自动记在 `config/ld_emulator.local.json`**，不回写这里 |
| `batch_start_num` | 批量创建/启动数量 |
| `backup_start_id` / `backup_end_id` | 备份/还原的 ID 范围 |
| `backup_path` | 备份目录；留空则备份时报「未配置」而不是静默失败 |
| `emulator_apk` | 批量安装的 APK 列表 |
| `emulator_install_path` | APK 所在目录；留空则装包时报「未配置」 |
| `image_path` | 模板图片根目录（现为 `assets/image/`，相对脚本目录） |
| `emulator_coord_info_map` | 坐标与布局参数（分辨率/DPI 变化时需重新核对） |

三个路径字段都支持 `~`、`%LOCALAPPDATA%`、`$HOME` 展开，相对路径按 `tools/ld_emulator/` 解析。
也可以不建 local 文件，直接 `set LDPLAYER_DIR=D:\leidian\LDPlayer9` 让 CLI 后端自己找。

### 注意事项

- **GUI 自动化**：运行后会自动操作鼠标键盘，期间请勿抢占鼠标。
- **两种中断方式**：把鼠标移到屏幕左上角（`pyautogui.FAILSAFE`），或按 **F8**。
- **分辨率/DPI 敏感**：模板匹配与固定坐标都依赖当前 1920×1080 @100% 的显示设置，换机器前先核对 `emulator_coord_info_map`。

---

## WorkBuddy 积分签到（tools/wb_reward）

调用 `workbuddy-reward-helper` skill 完成签到 / 旅行 / 成长计划，由 **Windows 计划任务**驱动，WorkBuddy 客户端不开也能跑。细节见 [`tools/wb_reward/README.md`](tools/wb_reward/README.md)。

| 命令 | 说明 |
|---|---|
| `mise run wb:all` | 签到 + 旅行（默认动作） |
| `mise run wb:checkin` / `wb:travel` / `wb:growth` | 单项执行 |
| `mise run wb:health` | 登录态健康检查（token 有效期 + 只读探活） |
| `mise run wb:status` | 只读探活 |

10 个时间点（健康 07:45；签到 09:00/13:00/20:00；旅行 08:15/12:30/16:45/21:00；成长 10:00/19:30）由 [`script/setup_wb_tasks.ps1`](script/setup_wb_tasks.ps1) 注册，动作指向 `.venv\Scripts\pythonw.exe -m tools.wb_reward <动作>`，无控制台窗口。

---

## 汽水音乐自动看广告（tools/qishui_auto）

手机开 USB 调试连电脑、保持亮屏停在看广告页面，脚本按 **截图 + OCR** 识别界面并替你点
「领取奖励 / 领取成功 × / 跳过 / 取消」。纯 UI 自动化：不改 App、不伪造进度、不加速播放。
细节见 [`tools/qishui_auto/README.md`](tools/qishui_auto/README.md)。

| 命令 | 说明 |
|---|---|
| `mise run qs:setup` | 首次：装 OCR 依赖（opencv / numpy / rapidocr） |
| `mise run qs:check` | 自检：adb / 设备 / 分辨率 / OCR / 当前屏幕识别到什么（**不点击**） |
| `mise run qs:dry` | 试跑：只识别不点击，先确认「它会点哪儿」 |
| `mise run qs:run` | 正式跑；`Ctrl + C` 停止（会恢复音量） |
| `mise run qs:devices` | 列出 adb 在线设备（只读） |

底层写法：`uv run --extra ocr python -m tools.qishui_auto [run|check|devices]`，支持
`--serial` / `--dry-run` / `--max-clicks N` / `--mute` / `--no-uia` / `--adb <路径>`。
Windows 双击：`script/汽水看广告.bat`。

点击优先级：**取消（拦截进入直播间）> 领取奖励/继续观看 > 领取成功 ×/退出不看了 > 跳过**。
文案随 App 版本会变，改 `config/qishui.json` 即可；本机 adb 路径与设备序列号写
`config/qishui.local.json`（已 gitignore）。

## 文档

| 文档 | 内容 |
|---|---|
| [`docs/项目结构规范.md`](docs/项目结构规范.md) | 多脚本仓库的目录/依赖/命名/入口规范 |
| [`docs/依赖重构清单.md`](docs/依赖重构清单.md) | 依赖兼容性评估、风险清单、分阶段改造 |
| [`docs/替代库选型建议.md`](docs/替代库选型建议.md) | 用 ldconsole/ADB 替代 GUI 点击的选型方案 |
| [`docs/项目代码审查报告.md`](docs/项目代码审查报告.md) | 逻辑与健壮性问题清单 |
