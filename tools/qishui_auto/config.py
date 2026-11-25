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
from tools.qishui_auto.match import Rule

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
    },
    # ---------- 点击目标 ----------
    "targets": {
        "reward": ["领取奖励", "继续观看"],
        "close": ["领取成功", "退出不看了"],
        "skip": ["跳过广告", "跳过", "关闭广告"],
        "cancel": "取消",
        "live_enter_keyword": "进入直播间",
    },
    "enable_skip": True,  # 提前点跳过有可能拿不到奖励；不放心就改 false
    "center_targets": ["领取奖励", "继续观看"],  # 这些取最靠近屏幕中心的一条
    "roi": {
        "领取奖励": {"x": [0.20, 0.80], "y": [0.30, 0.78]},
        "继续观看": {"x": [0.20, 0.80], "y": [0.30, 0.78]},
        "领取成功": {"x": [0.55, 1.00], "y": [0.00, 0.20]},
        "退出不看了": {"x": [0.00, 1.00], "y": [0.80, 1.00]},
        "跳过广告": {"x": [0.55, 1.00], "y": [0.00, 0.20]},
        "跳过": {"x": [0.55, 1.00], "y": [0.00, 0.20]},
        "关闭广告": {"x": [0.55, 1.00], "y": [0.00, 0.20]},
    },
    # ---------- 节奏 ----------
    "timing": {
        "poll_interval": 0.1,  # 每轮间隔（截图 + OCR 本身约 0.8~1.5s）
        "click_cooldown": 0.4,  # 点击后冷却，防止连点
        "dedupe_seconds": 3.0,  # 同目标同坐标在此时间内不重复点
        "uia_timeout": 4,  # uiautomator 单次超时
        "uia_max_fail": 3,  # 连续失败几次后本次会话关闭该通道
        "idle_report_every": 10,  # 每空转多少轮打一次心跳
    },
    # ---------- 行为 ----------
    "mute_on_start": False,  # 广告期间静音（退出恢复）
    "dry_run": False,  # 只识别不点击，安全试跑
    "max_clicks": 0,  # 点够多少次自动停；0 = 不限
    "debug": {"save_click_images": True},  # 命中时把标注截图存到 logs/qishui_auto/debug_clicks/
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

    ocr_min_score: float = 0.5
    ocr_max_width: int = 720
    ocr_use_cls: bool = False
    fuzzy: bool = True

    poll_interval: float = 0.1
    click_cooldown: float = 0.4
    dedupe_seconds: float = 3.0
    uia_timeout: int = 4
    uia_max_fail: int = 3
    idle_report_every: int = 10

    mute_on_start: bool = False
    dry_run: bool = False
    max_clicks: int = 0
    save_click_images: bool = True

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


def from_dict(cfg: dict) -> Settings:
    """dict → Settings。缺字段一律回落到 DEFAULTS。"""
    merged = _deep_merge(DEFAULTS, cfg or {})
    targets = merged.get("targets") or {}
    channels = merged.get("channels") or {}
    ocr = merged.get("ocr") or {}
    timing = merged.get("timing") or {}
    debug = merged.get("debug") or {}

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
        ocr_min_score=_number(ocr.get("min_score"), 0.5),
        ocr_max_width=max_width,
        ocr_use_cls=bool(ocr.get("use_cls", False)),
        fuzzy=bool(ocr.get("fuzzy", True)),
        poll_interval=max(0.02, _number(timing.get("poll_interval"), 0.1)),
        click_cooldown=max(0.0, _number(timing.get("click_cooldown"), 0.4)),
        dedupe_seconds=max(0.0, _number(timing.get("dedupe_seconds"), 3.0)),
        uia_timeout=max(1, int(_number(timing.get("uia_timeout"), 4))),
        uia_max_fail=max(1, int(_number(timing.get("uia_max_fail"), 3))),
        idle_report_every=max(1, int(_number(timing.get("idle_report_every"), 10))),
        mute_on_start=bool(merged.get("mute_on_start", False)),
        dry_run=bool(merged.get("dry_run", False)),
        max_clicks=max(0, int(_number(merged.get("max_clicks"), 0))),
        save_click_images=bool(debug.get("save_click_images", True)),
    )


def load() -> Settings:
    """读 config/qishui.json 并叠加 qishui.local.json。文件缺失也能跑（全默认值）。"""
    return from_dict(load_json_config(CONFIG_FILE))
