# wb_reward —— WorkBuddy 积分任务调度包装器

调用 `workbuddy-reward-helper` skill 完成每日签到 / 旅行 / 成长计划领取，
由 **Windows 计划任务**在工作日固定时间拉起，不依赖 WorkBuddy 客户端是否开着。

迁移自 `D:\workplace\WorkBuddy\wb_reward_runner.py`（2026-11-05），逻辑等价但做了下面的改造。

## 运行

```sh
mise run wb:all        # 签到 + 旅行（默认）
mise run wb:checkin    # 签到
mise run wb:travel     # 旅行
mise run wb:growth     # 成长计划（有可领档位才领）
mise run wb:health     # token 剩余有效期 + 只读探活
mise run wb:status     # 只读探活
```

底层等价写法：`uv run python -m tools.wb_reward <动作>`

## 配置（config/wb_reward.json）

配置统一放在仓库根 `config/` 下（见 [`config/README.md`](../../config/README.md)）；
需要覆盖时新建 `config/wb_reward.local.json`（已 gitignore），同名字段优先生效。

| 字段 | 说明 |
|---|---|
| `skill_scripts` | `workbuddy-reward-helper` 的 scripts 目录；留空则自动探测 `~/.workbuddy/skills/...` |
| `python` | 子进程解释器；**留空 = 当前解释器（项目 .venv）**，一般不用填 |
| `run_timeout` | 单次 skill 调用超时（秒），默认 180 |
| `retry_max` / `retry_delay` | 传输层瞬时故障的重试次数与间隔；401 等业务错误不重试 |
| `lock_timeout` | 运行锁最长等待（秒），超时则本次跳过（退出码 5） |
| `log_max_bytes` / `log_max_lines` | 日志轮转阈值与行数上限 |
| `token_info` | 登录态信息文件；留空则用 `%LOCALAPPDATA%\CodeBuddyExtension\...\workbuddy-desktop.info` |

## 相对迁移前的改动

1. **不再写死 WorkBuddy 内置 Python**（`...\binaries\python\versions\3.13.12\...`）——
   客户端升级后那个版本号目录就会变，任务会静默失败。现在用项目 `.venv` 的解释器。
2. 路径 / 超时 / 重试 / 日志上限全部外置到 `config/wb_reward.json`。
3. **新增跨任务运行锁**：签到和旅行的触发时间可能很近，而计划任务的
   `MultipleInstances` 只在同一任务内生效，不同任务会并发跑同一套凭据逻辑。
   现在同一时刻只允许一个实例，进程崩溃留下的陈旧锁会按 PID 自动回收。
4. 客户端存活探测改用 `psutil`，不再每轮 fork 一个 `tasklist` 进程。
5. 退出码语义统一，计划任务历史里能一眼看出失败类型。

日志格式保持原样：**按执行块整体置顶**（最新一次在最前，块内保序），带 1MB 轮转与 2000 行上限。

**日志是中文的**：`scheduler.log` 把 skill 返回的 JSON 翻译成一句话结论，例如

```
[2026-11-05 15:09:21] 开始执行：登录态检查（WorkBuddy 客户端：运行中）
[2026-11-05 15:09:21] 登录有效期至 2026-12-05 15:02，剩余 30.0 天
[2026-11-05 15:09:21] 探活结果：今日未签到；连续 0 天；今日旅行已达上限
[2026-11-05 15:09:21] 执行结束：成功，耗时 1.4 秒
```

只有在**执行失败**或**遇到未知状态**时，才追加一行原始 JSON 供排查。

> `result.log` 是 skill 自己写的（英文状态码，如 `checkin success credit=100`），本脚本只负责
> 把它的输出目录重定向到这里，不往里插内容（避免两个写入方互相覆盖）。想看中文请读 `scheduler.log`。

### 一个上游字段坑（别被误导）

签到状态查询返回的 `today_checked_in` **不可靠**：skill 源码注释写明「v5.3.8 实测签到成功后
该字段仍可能为 false」。因此：

- **判断今天签没签到，看 `checkin` 任务的结果**（`success` / `already_checked` 都算已签）；
- `status` / `health` 里的这条只作参考，日志已改成「签到接口未记录（该字段已知不准，以「签到」任务结果为准）」，
  不会再误报成「今日未签到」。

日志位置：**仓库根目录 `logs/wb_reward/`**（不在工具目录内）。这是全仓库统一约定——
所有脚本的运行时日志都放 `logs/<脚本名>/`，排查时只看一个地方，`.gitignore` 也只需一条规则。

## 计划任务

`script/setup_wb_tasks.ps1` 可一键重建/更新 10 个任务（健康检查、签到×3、旅行×4、成长×2），
指向 `.venv\Scripts\pythonw.exe -m tools.wb_reward <动作>`，工作目录为仓库根。
