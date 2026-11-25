# qishui_auto —— 汽水音乐自动看广告

纯 UI 自动化：**只点击界面上真实存在的按钮**。不改 App、不伪造观看进度、不加速播放，
广告该播多久还是多久，脚本只替你点「领取奖励 / 领取成功 × / 跳过 / 取消」。

## 原理

| 通道 | 做法 | 说明 |
|---|---|---|
| **OCR（主）** | `adb exec-out screencap -p` + RapidOCR | 视频广告是持续渲染的 SurfaceView，`uiautomator` 等不到 idle，实测必失败，所以 OCR 才是主通道 |
| uiautomator（兜底） | `adb shell uiautomator dump` | 只能读活动窗口，**读不到奖励弹窗**（覆盖层）；连续失败 3 次自动关闭。默认 `auto` 探测 |
| 静音（可选） | `input keyevent 164` | `MUTE_ON_START` 打开时，退出会恢复原音量 |

一轮 = 截图（0.5～1.6s）+ OCR（1.4～3.2s）→ 决策 → 点击，约 3～4s。

其中截图和 OCR 是大头，`poll_interval` 只占几十毫秒——想更快要动这两处（见「提速」）。

## 点击优先级

```
取消（拦截「xx秒后进入直播间」） > 领取奖励/继续观看/继续互动
    > 领取成功 ×/退出不看了 > 跳过
```

- 弹窗和广告结束页同时可见时，**先点「领取奖励」**，不会去点背后那个「领取成功」；
- `4s后进入直播间 [取消]` 会先点「取消」，不被自动带进直播间（兼容 `4s`/`4秒`/`4S`）；
- 万一点歪被带进直播间，会自动按返回键退出来继续看广告（见「误入直播间自救」）；
- 真进了直播间弹出「为你精选以下直播」时点「退出不看了」。

## 用法

前提：手机开 USB 调试并连上（`adb devices` 能看到）、**保持亮屏不锁屏**、App 停在看广告页面。

```sh
mise run qs:setup          # 首次：装 OCR 依赖（opencv / numpy / rapidocr）
mise run qs:check          # 自检：adb / 设备 / 分辨率 / OCR / 当前屏幕识别到什么（不点击）
mise run qs:dry            # 试跑：只识别不点击，先确认「它会点哪儿」
mise run qs:run            # 正式跑；Ctrl+C 停止（会恢复音量）
mise run qs:devices        # 列出 adb 在线设备
```

等价的底层写法：`uv run --extra ocr python -m tools.qishui_auto [run|check|devices]`，
参数：`--serial`（多设备）、`--dry-run`、`--max-clicks N`、`--mute`、`--no-uia`、`--adb <路径>`。

退出码：`0` 成功 ｜ `1` 参数/配置错误 ｜ `2` 运行失败（无 adb / 设备离线 / OCR 不可用）。

## 配置（config/qishui.json）

文案随 App 版本变，改配置就行，不用动代码。本机私有值（adb 路径、设备序列号）写
`config/qishui.local.json`。

| 字段 | 作用 |
|---|---|
| `adb_path` | adb 可执行文件；留空自动探测（PATH → `LDPLAYER_DIR` → 雷电目录） |
| `serial` | 指定设备；单设备留空即可 |
| `targets.reward` | 领奖按钮文案，如「领取奖励」「继续观看」 |
| `targets.close` | 广告结束页的「领取成功 ×」胶囊 + 直播面板「退出不看了」 |
| `targets.skip` / `enable_skip` | 是否自动点「跳过」；提前跳过可能拿不到奖励，不放心就关掉 |
| `center_targets` | 多命中时取最靠近屏幕中心的一条（领奖按钮居中且最大） |
| `roi` | 各目标允许点击的相对区域（0~1），防误点 |
| `ocr` | `min_score` / `max_width`（低于 600 会漏「取消」这类小字，加载时自动抬到 600）/ `use_cls` / `fuzzy` |
| `ocr.scan_top` / `scan_bottom` | 只识别这一段纵向区域（0~1）。底部商品卡/聊天没人点，裁掉能省两成 OCR 时间 |
| `ocr.full_scan_after_idle` | 空转多少帧后补一次整屏识别，兜住只出现在最底部的按钮（如「退出不看了」）；0 = 不回退 |
| `timing` | 轮询间隔、点击冷却、同坐标去重窗口、uia 超时与失败阈值 |
| `live_room` | 误入直播间自救：`escape` 开关、画面特征文案、前台 Activity 关键字、返回键次数、右上角关闭坐标 |
| `mute_on_start` | 广告期间静音，退出恢复 |
| `dry_run` / `max_clicks` | 只识别不点击 / 点够 N 次自动停 |
| `debug.save_click_images` | 命中时把标注截图存到 `logs/qishui/debug_clicks/` |
| `debug.clear_on_start` | 每次启动清掉上次的截图（一张 1~4MB，不清会越攒越多） |
| `debug.keep_files` | 启动清理时保留最新几张；0 = 全清 |
| `debug.max_total_mb` | 运行中目录总量上限，超出删最旧的；0 = 不限 |
| `debug.trim_every` | 每写多少张图检查一次总量 |

## 输出

- 运行日志：`logs/qishui/run.log`（同时打到控制台）
- 命中截图：`logs/qishui/debug_clicks/`（点错位置时先看这里的图，再调 `roi`）
  - 每次启动自动清理，不手动删也不会无限增长；想留现场就调 `keep_files`
- 结束摘要：每个目标点了几次、退出直播间几次、识别多少帧、总耗时

## 提速

实测各环节耗时（1440×3200 手机，逻辑分辨率同）：

| 环节 | 耗时 | 说明 |
|---|---|---|
| `poll_interval` | 0.05s | **不是瓶颈**，占比不到 3% |
| adb 截图 | 1.55s | 系统开销，只能少截 |
| OCR 整屏 | 1.65～3.2s | 主要瓶颈，靠 `scan_bottom` 裁剪缓解 |
| 保存调试图 | 0.17s | 已改后台线程，不阻塞主循环 |

想再快可以动这些地方：裁剪比例（`ocr.scan_bottom`）、`max_width`，
或者把采集从 `screencap` 换成 scrcpy/minicap 视频流（工作量大，未做）。

## 误入直播间自救

广告中途会弹「`6s后进入直播间 [取消]`」。万一没点中取消被带进直播间，
那里**只有聊天和商品，没有任何可点按钮**，不处理就会一直空转。

判定要两条同时成立才动手（避免把「加载中」误判成直播间）：

1. 画面特征命中 ≥2 个（`live_room.hints`：更多直播 / 人气榜 / 说点什么 / 本场点赞）；
2. `dumpsys window` 的前台 Activity 含直播间关键字（`live_room.activity_keys`）。

确认后先按返回键（实测一次就回到广告页），无效才点右上角 X。整个动作有冷却，
不会连续触发。不想用就把 `live_room.escape` 设 `false`。

## 踩过的坑（改代码前先看）

- **分辨率**：`wm size` 会同时报 `Physical size` 和 `Override size`，`screencap`/`input tap` 用的是
  **Override（逻辑分辨率）**，所以取最后一个匹配值。脚本另外以截图实际尺寸为准。
- **uiautomator 不能当主通道**：它读不到奖励弹窗，放在 OCR 前面会一直点「领取成功」而不点
  「领取奖励」，卡死循环。
- **领奖优先于跳过**：两者同时出现先点「领取奖励」，否则「跳过」会把奖励点没。
- **锁屏**：锁屏后截到的是锁屏界面，脚本会空转（日志每 10 轮提示一次「等待中」）。
- **`input keyevent 164`** 是唯一可靠的静音方式：`cmd media_session volume --set` 在部分设备不生效。
- **标题里的词不是按钮**：`完成互动，领取奖励福利` 含「领取奖励」子串，但点它毫无反应。
  所以 `text_match` 要求目标词落在整段的**开头或结尾**，夹在句子中间的一律不算。
- **弹窗按钮要在按钮上点，不是标题上**：`继续互动` / `领取奖励` 这类按钮常紧挨一行说明文字，
  两者 ROI 都覆盖时靠 `center_targets` 取最靠近屏幕中心那条。
- **点歪会被带进直播间**：`6s后进入直播间 [取消]` 的「取消」常被 OCR 读成「肖」这类单字，
  所以除了精确匹配，还按「倒计时胶囊右侧最右的短文本」兜底定位。

## 排错

| 现象 | 处理 |
|---|---|
| `截图失败（累计 N 次）` | `adb devices` 是否在线、手机是否锁屏 |
| 一直不点 | App 升级后文案变了，改 `targets.*`；先跑 `qs:check` 看识别结果 |
| 点错位置 | 看 `logs/qishui/debug_clicks/` 的标注图，调 `roi` |
| 同一个按钮连点不动 | 日志会提示「已经连点 N 次」——多半点在标题等非按钮文字上，检查 `text_match` 的目标词位置 |
| 日志出现「检测到误入直播间」 | 说明「取消」没点中，已自动退出；若频繁出现就调 `roi` 里 `取消` 的匹配 |
| `OCR 不可用` | `mise run qs:setup`；Python 3.14 可能没有 onnxruntime 轮子，用 3.13 |
| 磁盘被调试图占满 | 默认启动就清、运行中限量；确认 `debug.clear_on_start` 没被关掉 |

## 单元测试

```sh
mise run test     # tests/test_qishui_match.py（决策纯逻辑 / 匹配优先级）
                  # tests/test_qishui_config.py（配置默认值不漂移）
                  # tests/test_qishui_ocr.py（合成截图 → 真实 OCR → 决策 / 裁剪坐标还原）
                  # tests/test_qishui_runner.py（去重 / 上限 / dry-run / 直播间自救 / 异步存图）
                  # tests/test_qishui_debug_cleanup.py（调试图清理与总量限制）
```

OCR 集成测试需要中文字体（Windows 用微软雅黑），没有字体或未装 OCR 依赖时自动 skip。

## 来源

参考 [cvabm/qishui](https://github.com/cvabm/qishui) 的单文件脚本重写：识别/点击策略保持一致，
把参数外置到 `config/`，补了自检、dry-run、日志落盘、点击去重与统计。
