# -*- coding: utf-8 -*-
"""主循环编排测试：模拟 adb，不连手机、不跑 OCR。

覆盖三件容易写错的事：重复点击抑制、点击上限、dry-run 不落地点击。
OCR 识别本身由 test_qishui_ocr.py 覆盖，这里把「截图 → 识别」换成固定输入，
顺带让这组用例不依赖 OCR 模型（跑得快）。
"""

import numpy as np

from tools.qishui_auto import runner as runner_mod
from tools.qishui_auto.config import from_dict
from tools.qishui_auto.match import Decision
from tools.qishui_auto.runner import Runner

W, H = 1080, 2400
REWARD = Decision("reward", "领取奖励", "领取奖励", 540, 1500)


class FakeAdb:
    """只记点击，不执行任何命令。"""

    def __init__(self, png: bytes | None = b"\x89PNG\r\n\x1a\nfake"):
        self.png = png
        self.taps: list[tuple[int, int]] = []
        self.exe = "fake-adb"
        self.serial = None

    def ensure_device(self, serial=None):
        self.serial = "fake-device"
        return "fake-device", ""

    def screen_size(self):
        return W, H

    def capture_png(self):
        return self.png

    def tap(self, x, y):
        self.taps.append((x, y))
        return True

    def media_volume(self):
        return 8

    def toggle_mute(self):
        return True

    def run(self, *args, **kwargs):
        return None


def make_runner(monkeypatch, decision=REWARD, png=b"\x89PNG\r\n\x1a\nfake", **overrides) -> Runner:
    """造一个 runner：adb 换假实现，截图/识别换成固定结果。"""
    settings = from_dict(
        {
            "debug": {"save_click_images": False},  # 测试不落盘
            "timing": {"poll_interval": 0.01, "click_cooldown": 0.01},
            **overrides,
        }
    )
    instance = Runner(settings)
    instance.adb = FakeAdb(png=png)
    instance.ocr.nodes = lambda image: []  # 不加载模型
    monkeypatch.setattr(runner_mod, "decode_png", lambda raw: np.zeros((H, W, 3), dtype=np.uint8))
    monkeypatch.setattr(runner_mod, "decide", lambda *a, **k: decision)
    return instance


def test_click_is_executed_once(monkeypatch):
    instance = make_runner(monkeypatch)
    assert instance._step() is True
    assert instance.adb.taps == [(540, 1500)]
    assert instance.stats["reward"] == 1


def test_duplicate_click_is_suppressed(monkeypatch):
    instance = make_runner(monkeypatch)
    instance._step()
    assert instance._step() is False  # 同一目标同一位置，冷却期内不重复点
    assert len(instance.adb.taps) == 1


def test_duplicate_allowed_after_dedupe_window(monkeypatch):
    instance = make_runner(monkeypatch, timing={"dedupe_seconds": 0, "poll_interval": 0.01, "click_cooldown": 0.01})
    instance._step()
    assert instance._step() is True
    assert len(instance.adb.taps) == 2


def test_dry_run_counts_but_does_not_tap(monkeypatch):
    instance = make_runner(monkeypatch, dry_run=True)
    assert instance._step() is True
    assert instance.adb.taps == []
    assert instance.stats["reward"] == 1


def test_no_decision_does_nothing(monkeypatch):
    instance = make_runner(monkeypatch, decision=None)
    assert instance._step() is False
    assert instance.adb.taps == []


def test_run_stops_at_max_clicks(monkeypatch):
    instance = make_runner(
        monkeypatch,
        max_clicks=1,
        timing={"dedupe_seconds": 0, "poll_interval": 0.01, "click_cooldown": 0.01},
    )
    assert instance.run() == 0
    assert len(instance.adb.taps) == 1


def test_limit_disabled_by_default(monkeypatch):
    instance = make_runner(monkeypatch)
    assert instance._limit_reached() is False


def test_capture_failure_does_not_crash(monkeypatch):
    instance = make_runner(monkeypatch, png=None)
    assert instance._step() is False
    assert instance.capture_fail == 1
