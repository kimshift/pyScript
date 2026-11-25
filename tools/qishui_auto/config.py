# -*- coding: utf-8 -*-
"""config/qishui.json 的加载与默认值。

配置分两层（见 config/README.md）：
    config/qishui.json         入库的通用值
    config/qishui.local.json   本机私有覆盖（adb 路径、设备序列号），已 gitignore

文案随 App 版本会变，改配置就够了，不用动代码。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from kit.config import load_config as load_json_config
from kit.paths import config_path, log_dir
from tools.qishui_auto.match import Overlay, Rule

TOOL_NAME = "qishui"
CONFIG_FILE = config_path(TOOL_NAME)

DEFAULTS: dict = {
    # ---------- 设备 ----------
    "adb_path": "",  # 留空 = 自动探测（PATH → LDPLAYER_DIR → 雷电常见目录）
    "serial": "",  # 多设备时必须指定；单设备留空自动取
    # ---------- 识别通道 ----------
    "channels": {
        "ocr": True,  # 主通道
        "uiautomator": "auto",  # auto / on / off：只能读广告结束页，读不到奖励弹窗
    },
    "ocr": {
        "min_score": 0.5,
        "max_width": 720,  # 缩放宽度；低于 600 会漏「取消」这类小字
        "use_cls": False,  # 关方向分类，省约 0.2s/帧
        "fuzzy": True,
        # 常规帧只识别这一段纵向区域（0~1）。按钮都在上面：顶部状态条/跳过在最上，
        # 领奖弹窗在中段；底部是商品卡和聊天，几十行字没人点，裁掉能省一半多时间。
        "scan_top": 0.0,
        "scan_bottom": 0.90,
        # 连续这么多帧都没扫到可点目标时，改回整屏扫一次：兜住只出现在最底部的
        # 按钮（如「退出不看了」），平时不为它付整屏 OCR 的代价。0 = 不回退。
        "full_scan_after_idle": 6,
    },
    # ---------- 点击目标 ----------
    "targets": {
        "reward": ["领取奖励", "继续观看", "继续互动"],
        "close": ["领取成功", "退出不看了"],
        "skip": ["跳过广告", "跳过", "关闭广告"],
        "cancel": "取消",
        "live_enter_keyword": "进入直播间",
    },
    "enable_skip": True,  # 提前点跳过有可能拿不到奖励；不放心就改 false
    "center_targets": ["领取奖励", "继续观看", "继续互动"],  # 这些取最靠近屏幕中心的一条
    "roi": {
        "领取奖励": {"x": [0.20, 0.80], "y": [0.30, 0.78]},
        "继续观看": {"x": [0.20, 0.80], "y": [0.30, 0.78]},
        "继续互动": {"x": [0.20, 0.80], "y": [0.25, 0.78]},
        "领取成功": {"x": [0.55, 1.00], "y": [0.00, 0.20]},
        "退出不看了": {"x": [0.00, 1.00], "y": [0.80, 1.00]},
        "跳过广告": {"x": [0.55, 1.00], "y": [0.00, 0.20]},
        "跳过": {"x": [0.55, 1.00], "y": [0.00, 0.20]},
        "关闭广告": {"x": [0.55, 1.00], "y": [0.00, 0.20]},
    },
    # ---------- 节奏 ----------
    "timing": {
        "poll_interval": 0.05,  # 空转时的间隔；一帧本身就要 2~3s，这里不用留太大
        "click_cooldown": 0.2,  # 点完立刻截下一帧，冷却只用来等界面响应
        "modal_cooldown": 0.0,  # 中间弹窗点了即消失，不用等
        "modal_dedupe": 0.5,  # 弹窗类目标的去重窗口（小于一帧耗时，挡住同屏重复点即可）
        "dedupe_seconds": 2.0,  # 同目标同坐标在此时间内不重复点
        "stuck_repeat": 3,  # 同一按钮连续点几次还没变化就算卡住
        "uia_timeout": 4,  # uiautomator 单次超时
        "uia_max_fail": 3,  # 连续失败几次后本次会话关闭该通道
        "uia_after_idle": 4,  # 连续空转多少轮后才启用 uiautomator（它一次能卡 4~11s，别挡主循环）
        "uia_interval": 10.0,  # 两次 uiautomator 尝试的最小间隔
        "idle_report_every": 10,  # 每空转多少轮打一次心跳
    },
    # ---------- 误入直播间自救 ----------
    "live_room": {
        "escape": True,  # 万一被带进直播间，自动退出来继续看广告
        "hints": ["更多直播", "人气榜", "说点什么", "本场点赞"],  # 画面特征，命中 2 个才算
        "activity_keys": ["LivePlayerActivity", "com.luna.biz.live"],  # 前台 Activity 关键字（二次确认）
        "back_max": 2,  # 先试几次返回键
        "close_x": 0.94,  # 返回键无效时点右上角 X（相对坐标）
        "close_y": 0.08,
        "wait": 1.0,  # 退出动作后等界面切换
        "cooldown": 3.0,  # 两次自救之间的最小间隔
    },
    # ---------- 覆盖层弹窗（纯图片、按钮无文字） ----------
    # 这类弹窗唯一的文字按钮是「点击使用」，点进去会跳商品页；真正的关闭是个
    # 没有文字的圆形 X，OCR 认不出来，只能按相对坐标点。
    "overlays": [
        {
            "name": "优惠券",
            "enabled": True,
            "hints": ["天降福利", "点击使用", "满减券"],  # 命中 need 个就认为它在
            "need": 2,
            "close_x": 0.50,  # 卡片下方圆形 X
            "close_y": 0.83,
            "cooldown": 5.0,
        },
    ],
    # ---------- 行为 ----------
    "mute_on_start": False,  # 广告期间静音（退出恢复）
    "dry_run": False,  # 只识别不点击，安全试跑
    "max_clicks": 0,  # 点够多少次自动停；0 = 不限
    "debug": {
        "save_click_images": True,  # 命中时把标注截图存到 logs/qishui/debug_clicks/
        "clear_on_start": True,  # 每次运行前清掉上次留下的截图（一张 1~4MB，不清会越攒越多）
        "keep_files": 0,  # 启动清空时保留最新几张；0 = 全清
        "max_total_mb": 512,  # 运行中目录总量上限，超出就删最旧的；0 = 不限
        "trim_every": 50,  # 每点多少次检查一次总量
    },
}


def _number(value, default: float) -> float:
    """取数值：0 是合法值（如 dedupe_seconds=0 表示不去重），只有 None/空串才回落默认。"""
    if value is None or value == "":
        return default
    return float(value)


def _deep_merge(base: dict, override: dict) -> dict:
    """把 override 递归合并进 base（返回新 dict，不改原对象）。"""
    out = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


@dataclass
class Settings:
    adb_path: str = ""
    serial: str = ""
    use_ocr: bool = True
    uia_mode: str = "auto"

    reward_targets: list[str] = field(default_factory=list)
    close_targets: list[str] = field(default_factory=list)
    skip_targets: list[str] = field(default_factory=list)
    enable_skip: bool = True
    cancel_word: str = "取消"
    live_keyword: str = "进入直播间"
    center_targets: list[str] = field(default_factory=list)
    roi: dict = field(default_factory=dict)
    overlays: list[Overlay] = field(default_factory=list)

    ocr_min_score: float = 0.5
    ocr_max_width: int = 720
    ocr_use_cls: bool = False
    fuzzy: bool = True
    ocr_scan: tuple[float, float] = (0.0, 0.90)
    ocr_full_scan_after_idle: int = 6

    @property
    def ocr_crop(self) -> tuple[float, float]:
        """常规帧的识别区域；覆盖整屏时返回 None，交给 OCR 走最快路径。"""
        top, bottom = self.ocr_scan
        return None if top <= 0.0 and bottom >= 1.0 else (top, bottom)

    poll_interval: float = 0.1
    click_cooldown: float = 0.4
    modal_cooldown: float = 0.15
    modal_dedupe: float = 0.8
    dedupe_seconds: float = 3.0
    stuck_repeat: int = 3
    uia_timeout: int = 4
    uia_max_fail: int = 3
    uia_after_idle: int = 4
    uia_interval: float = 10.0
    idle_report_every: int = 10

    live_escape: bool = True
    live_hints: list[str] = field(default_factory=list)
    live_activity_keys: list[str] = field(default_factory=list)
    live_back_max: int = 2
    live_close_x: float = 0.94
    live_close_y: float = 0.08
    live_wait: float = 1.0
    live_cooldown: float = 3.0

    mute_on_start: bool = False
    dry_run: bool = False
    max_clicks: int = 0
    save_click_images: bool = True
    clear_on_start: bool = True
    keep_files: int = 0
    max_total_mb: float = 512.0
    debug_trim_every: int = 50

    # ---------- 派生 ----------

    @property
    def rules(self) -> list[Rule]:
        """按优先级展开：领奖 → 关闭 → 跳过。"""
        rules: list[Rule] = []
        for action, targets in (
            ("reward", self.reward_targets),
            ("close", self.close_targets),
            ("skip", self.skip_targets if self.enable_skip else []),
        ):
            for target in targets:
                rules.append(
                    Rule(
                        action=action,
                        target=target,
                        roi=self.roi.get(target),
                        center=target in self.center_targets,
                    )
                )
        return rules

    @property
    def debug_dir(self) -> Path:
        return log_dir(TOOL_NAME, create=True) / "debug_clicks"

    @property
    def log_file(self) -> Path:
        return log_dir(TOOL_NAME, create=True) / "run.log"

    @property
    def uia_enabled(self) -> bool:
        return self.uia_mode in ("auto", "on", True)


def _uia_mode(value) -> str:
    """把 true/false/"auto" 归一成 auto/on/off。"""
    if value is True:
        return "on"
    if value is False or value is None:
        return "off"
    text = str(value).strip().lower()
    return text if text in ("auto", "on", "off") else "auto"


def _overlays(items) -> list[Overlay]:
    """把配置里的 overlays 列表转成 Overlay；缺名字/坐标的条目直接跳过（配错别崩）。"""
    out: list[Overlay] = []
    for item in items or []:
        if not isinstance(item, dict) or not item.get("enabled", True):
            continue
        name = str(item.get("name") or "").strip()
        hints = tuple(str(h).strip() for h in (item.get("hints") or []) if str(h).strip())
        if not name or not hints:
            continue
        try:
            close_x = min(1.0, max(0.0, _number(item.get("close_x"), 0.5)))
            close_y = min(1.0, max(0.0, _number(item.get("close_y"), 0.83)))
        except (TypeError, ValueError):
            continue
        out.append(
            Overlay(
                name=name,
                hints=hints,
                close=(close_x, close_y),
                need=max(1, int(_number(item.get("need"), 2))),
                cooldown=max(0.0, _number(item.get("cooldown"), 5.0)),
            )
        )
    return out


def _scan_range(top, bottom) -> tuple[float, float]:
    """归一化 OCR 扫描区域：夹到 0~1，且保证 top < bottom（写反了就自动换回来）。"""
    t = min(1.0, max(0.0, _number(top, 0.0)))
    b = min(1.0, max(0.0, _number(bottom, 0.90)))
    if t >= b:  # 配错方向时退回整屏，别让主循环一帧都认不出来
        return (0.0, 1.0)
    return (t, b)


def from_dict(cfg: dict) -> Settings:
    """dict → Settings。缺字段一律回落到 DEFAULTS。"""
    merged = _deep_merge(DEFAULTS, cfg or {})
    targets = merged.get("targets") or {}
    channels = merged.get("channels") or {}
    ocr = merged.get("ocr") or {}
    timing = merged.get("timing") or {}
    debug = merged.get("debug") or {}
    live = merged.get("live_room") or {}

    # 太窄会把「取消」这类小字漏掉，兜底抬到 600
    max_width = max(600, int(_number(ocr.get("max_width"), 720)))

    return Settings(
        adb_path=str(merged.get("adb_path") or ""),
        serial=str(merged.get("serial") or ""),
        use_ocr=bool(channels.get("ocr", True)),
        uia_mode=_uia_mode(channels.get("uiautomator", "auto")),
        reward_targets=list(targets.get("reward") or []),
        close_targets=list(targets.get("close") or []),
        skip_targets=list(targets.get("skip") or []),
        enable_skip=bool(merged.get("enable_skip", True)),
        cancel_word=str(targets.get("cancel") or "取消"),
        live_keyword=str(targets.get("live_enter_keyword") or "进入直播间"),
        center_targets=list(merged.get("center_targets") or []),
        roi=dict(merged.get("roi") or {}),
        overlays=_overlays(merged.get("overlays")),
        ocr_min_score=_number(ocr.get("min_score"), 0.5),
        ocr_max_width=max_width,
        ocr_use_cls=bool(ocr.get("use_cls", False)),
        fuzzy=bool(ocr.get("fuzzy", True)),
        ocr_scan=_scan_range(ocr.get("scan_top"), ocr.get("scan_bottom")),
        ocr_full_scan_after_idle=max(0, int(_number(ocr.get("full_scan_after_idle"), 6))),
        poll_interval=max(0.02, _number(timing.get("poll_interval"), 0.1)),
        click_cooldown=max(0.0, _number(timing.get("click_cooldown"), 0.4)),
        modal_cooldown=max(0.0, _number(timing.get("modal_cooldown"), 0.15)),
        modal_dedupe=max(0.0, _number(timing.get("modal_dedupe"), 0.8)),
        dedupe_seconds=max(0.0, _number(timing.get("dedupe_seconds"), 3.0)),
        stuck_repeat=max(1, int(_number(timing.get("stuck_repeat"), 3))),
        uia_timeout=max(1, int(_number(timing.get("uia_timeout"), 4))),
        uia_max_fail=max(1, int(_number(timing.get("uia_max_fail"), 3))),
        uia_after_idle=max(0, int(_number(timing.get("uia_after_idle"), 4))),
        uia_interval=max(0.0, _number(timing.get("uia_interval"), 10.0)),
        idle_report_every=max(1, int(_number(timing.get("idle_report_every"), 10))),
        live_escape=bool(live.get("escape", True)),
        live_hints=list(live.get("hints") or DEFAULTS["live_room"]["hints"]),
        live_activity_keys=list(live.get("activity_keys") or DEFAULTS["live_room"]["activity_keys"]),
        live_back_max=max(0, int(_number(live.get("back_max"), 2))),
        live_close_x=min(0.99, max(0.0, _number(live.get("close_x"), 0.94))),
        live_close_y=min(0.99, max(0.0, _number(live.get("close_y"), 0.08))),
        live_wait=max(0.0, _number(live.get("wait"), 1.0)),
        live_cooldown=max(0.0, _number(live.get("cooldown"), 3.0)),
        mute_on_start=bool(merged.get("mute_on_start", False)),
        dry_run=bool(merged.get("dry_run", False)),
        max_clicks=max(0, int(_number(merged.get("max_clicks"), 0))),
        save_click_images=bool(debug.get("save_click_images", True)),
        clear_on_start=bool(debug.get("clear_on_start", True)),
        keep_files=max(0, int(_number(debug.get("keep_files"), 0))),
        max_total_mb=max(0.0, _number(debug.get("max_total_mb"), 512.0)),
        debug_trim_every=max(1, int(_number(debug.get("trim_every"), 50))),
    )


def load() -> Settings:
    """读 config/qishui.json 并叠加 qishui.local.json。文件缺失也能跑（全默认值）。"""
    return from_dict(load_json_config(CONFIG_FILE))
