# config/ —— 所有脚本的配置集中在这里

每个脚本一份配置，命名 `<脚本名>.json`；机器私有的值放 `<脚本名>.local.json`（已被
`.gitignore` 忽略，不会提交）。代码通过 `kit.paths.config_path("<脚本名>")` 定位，
`kit.config.load_config()` 会自动把 local 叠加到公共配置之上。

## 新电脑拉下来怎么配

```bash
# 1. 装环境（只需要做一次）
mise install
mise run setup

# 2. 按需生成本机私有配置（模板就在旁边，改完别忘了删掉 .example 后缀里的示例值）
cp config/ld_emulator.local.example.json config/ld_emulator.local.json

# 3. 自检：不点鼠标，只验证依赖与配置能否加载
mise run ld:check
```

**只有雷电相关的三个路径需要改**，其余配置开箱即用：

| 字段 | 填什么 | 不填会怎样 |
|---|---|---|
| `emulator_path` | 雷电多开器 `dnmultiplayer.exe` 的完整路径 | 自动探测 `LDPLAYER_DIR` → PATH → 常见安装目录；都找不到则提示手动配置 |
| `backup_path` | 备份文件存放目录 | 备份/还原时报「未配置」 |
| `emulator_install_path` | APK 安装包所在目录 | 批量装包时报「未配置」 |

路径支持 `~`、`%LOCALAPPDATA%`、`C:\...` 三种写法，例如
`%LOCALAPPDATA%\leidian\LDPlayer9\dnmultiplayer.exe`。

## 文件说明

| 文件 | 是否入库 | 用途 |
|---|---|---|
| `ld_emulator.json` | ✅ | 雷电批量自动化的公共配置（后端、分辨率、坐标、APK 列表等） |
| `ld_emulator.local.json` | ❌ | 本机雷电路径 + **运行进度 `emulator_end_id`**，覆盖上面的同名字段 |
| `ld_emulator.local.example.json` | ✅ | 上者的模板，新机器复制后改名 |
| `wb_reward.json` | ✅ | 积分签到的超时/重试/日志上限；`skill_scripts` 留空即按用户目录自动探测 |
| `wb_reward.local.json` | ❌ | 需要覆盖解释器或 skill 路径时再建 |

> **运行状态也写进 `.local.json`。** 例如 `emulator_end_id`（已经创建到第几个模拟器）
> 由程序自己回写，只落本机；公共配置里保持 0 作为「从第一个开始」的起点。
> 这样跑完 create 后 `git status` 依旧是干净的。

> 铁律：`*.json`（公共）里**不允许**出现本机绝对路径，否则别人拉下来必然跑不通。
> 加新字段前先问一句：这个值换台电脑还成立吗？不成立就放 `.local.json`。
