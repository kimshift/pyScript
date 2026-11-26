# -*- coding: utf-8 -*-
"""主循环编排测试：模拟 adb，不连手机、不跑 OCR。

覆盖三件容易写错的事：重复点击抑制、点击上限、dry-run 不落地点击。
OCR 识别本身由 test_qishui_ocr.py 覆盖，这里把「截图 → 识别」换成固定输入，
顺带让这组用例不依赖 OCR 模型（跑得快）。
"""

import time

import numpy as np

from tools.qishui_auto import runner as runner_mod
from tools.qishui_auto.config import from_dict
from tools.qishui_auto.match import Decision, Node, live_room_hints
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

    def ensure_device(self, serial=None, prefer=None):
        self.serial = "fake-device"
        return "fake-device", ""

    def screen_size(self):
        return W, H

    def capture_png(self):
        return self.png

    def tap(self, x, y):
        self.taps.append((x, y))
        return True

    def back(self):
        return True

    def current_focus(self):
        return ""

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
    instance.ocr.nodes = lambda image, crop=None: []  # 不加载模型
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
    instance = make_runner(
        monkeypatch,
        timing={"dedupe_seconds": 0, "modal_dedupe": 0, "poll_interval": 0.01, "click_cooldown": 0.01},
    )
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


# ------------------------- 提速：OCR 裁剪 -------------------------


def test_scan_crop_comes_from_config(monkeypatch):
    instance = make_runner(monkeypatch, ocr={"scan_top": 0.0, "scan_bottom": 0.9})
    assert instance._scan_crop() == (0.0, 0.9)


def test_scan_crop_none_when_full_screen(monkeypatch):
    instance = make_runner(monkeypatch, ocr={"scan_top": 0.0, "scan_bottom": 1.0})
    assert instance._scan_crop() is None


def test_full_scan_kicks_in_after_idle(monkeypatch):
    """底部按钮（退出不看了）只在空转够久时补一次整屏，平时不为它付代价。"""
    instance = make_runner(monkeypatch, ocr={"scan_top": 0.0, "scan_bottom": 0.9, "full_scan_after_idle": 3})
    instance.idle = 0
    assert instance._full_scan_due() is False
    instance.idle = 2
    assert instance._full_scan_due() is False
    instance.idle = 3
    assert instance._full_scan_due() is True
    instance.idle = 6
    assert instance._full_scan_due() is True


def test_full_scan_disabled_by_zero(monkeypatch):
    instance = make_runner(monkeypatch, ocr={"full_scan_after_idle": 0})
    instance.idle = 100
    assert instance._full_scan_due() is False


def test_step_passes_crop_to_ocr(monkeypatch):
    instance = make_runner(monkeypatch, ocr={"scan_top": 0.0, "scan_bottom": 0.9})
    seen = []
    instance.ocr.nodes = lambda image, crop=None: seen.append(crop) or []
    instance._step()
    assert seen == [(0.0, 0.9)]


def test_step_falls_back_to_full_scan(monkeypatch):
    """裁片区里没找到目标、且空转够久时，应再整屏识别一次。"""
    instance = make_runner(monkeypatch, decision=None, ocr={"scan_top": 0.0, "scan_bottom": 0.9, "full_scan_after_idle": 2})
    seen = []
    instance.ocr.nodes = lambda image, crop=None: seen.append(crop) or []
    instance.idle = 2
    instance._step()
    assert seen == [(0.0, 0.9), None]  # 先裁剪，再补整屏


# ------------------------- 提速：调试图异步写 -------------------------


def test_debug_save_does_not_block_step(monkeypatch, tmp_path):
    """存图放后台线程：_step 返回时不该已经等完 0.17s 的 encode+落盘。"""
    written = []

    def slow_save(*args):
        time.sleep(0.3)
        written.append(args)

    instance = make_runner(monkeypatch, debug={"save_click_images": True})
    monkeypatch.setattr(runner_mod, "save_debug", slow_save)
    monkeypatch.setattr(type(instance.s), "debug_dir", property(lambda self: tmp_path))

    began = time.time()
    assert instance._step() is True
    assert time.time() - began < 0.25  # 没等写盘

    instance._flush_debug()  # 退出时补等，保证图真的落地
    assert len(written) == 1


def test_debug_save_failure_never_breaks_loop(monkeypatch, tmp_path):
    def boom(*args):
        raise OSError("磁盘满了")

    instance = make_runner(monkeypatch, debug={"save_click_images": True})
    monkeypatch.setattr(runner_mod, "save_debug", boom)
    monkeypatch.setattr(type(instance.s), "debug_dir", property(lambda self: tmp_path))

    assert instance._step() is True  # 点照常点
    instance._flush_debug()  # 线程里的异常不外溢


# ------------------------- 覆盖层弹窗（优惠券） -------------------------


OVERLAY = Decision("overlay", "优惠券", "（关闭按钮）", 540, 1992, "弹出优惠券，按坐标关闭")


def test_overlay_close_is_clicked(monkeypatch):
    instance = make_runner(monkeypatch, decision=OVERLAY)
    assert instance._step() is True
    assert instance.adb.taps == [(540, 1992)]
    assert instance.stats["overlay"] == 1


def test_overlay_close_has_cooldown(monkeypatch):
    """关闭按钮没生效时别连点同一坐标，冷却期内安静空转。"""
    instance = make_runner(
        monkeypatch,
        decision=OVERLAY,
        overlays=[{"name": "优惠券", "hints": ["天降福利"], "cooldown": 30}],
        timing={"modal_dedupe": 0, "poll_interval": 0.01, "click_cooldown": 0.01},
    )
    assert instance._step() is True
    assert instance._step() is False  # 冷却内不再点
    assert len(instance.adb.taps) == 1


def test_overlay_close_retries_after_cooldown(monkeypatch):
    instance = make_runner(
        monkeypatch,
        decision=OVERLAY,
        overlays=[{"name": "优惠券", "hints": ["天降福利"], "cooldown": 0}],
        timing={"modal_dedupe": 0, "poll_interval": 0.01, "click_cooldown": 0.01},
    )
    instance._step()
    assert instance._step() is True
    assert len(instance.adb.taps) == 2



# ------------------------- 中间弹窗节奏 -------------------------


def test_reward_modal_uses_short_dedupe_window(monkeypatch):
    """「领取奖励 / 继续观看」点完就消失，去重窗口要短，否则会干等好几秒。"""
    instance = make_runner(monkeypatch, timing={"modal_dedupe": 0.01, "poll_interval": 0.01, "click_cooldown": 0.01})
    instance._step()
    time.sleep(0.02)
    assert instance._step() is True
    assert len(instance.adb.taps) == 2


def test_close_still_uses_long_dedupe_window(monkeypatch):
    instance = make_runner(
        monkeypatch,
        decision=Decision("close", "领取成功", "领取成功", 1200, 216),
        timing={"modal_dedupe": 0.01, "dedupe_seconds": 5.0, "poll_interval": 0.01, "click_cooldown": 0.01},
    )
    instance._step()
    time.sleep(0.02)
    assert instance._step() is False
    assert len(instance.adb.taps) == 1


# ------------------------- 误入直播间自救 -------------------------


def live_nodes():
    return [
        Node("更多直播", 1214, 406),
        Node("人气榜", 163, 405),
        Node("说点什么", 209, 3095),
        Node("关注", 562, 259),
    ]


def test_live_room_hints_need_two_matches():
    assert live_room_hints(live_nodes(), ["更多直播", "人气榜", "说点什么", "本场点赞"]) is True
    assert live_room_hints([Node("更多直播", 10, 10)], ["更多直播", "人气榜"]) is False
    assert live_room_hints([], ["更多直播"]) is False


def test_escape_falls_back_to_close_button(monkeypatch):
    """返回键按了没用（仍停在直播间）时，改为点右上角关闭。"""
    instance = make_runner(monkeypatch, decision=None, live_room={"back_max": 1, "wait": 0, "cooldown": 0})
    backs = {"n": 0}
    instance.adb.back = lambda: backs.__setitem__("n", backs["n"] + 1) or True
    instance.adb.current_focus = lambda: "mCurrentFocus=Window{1 u0 com.luna.music/com.luna.biz.live.plugin.LunaDefaultLivePlayerActivity}"
    instance.ocr.nodes = lambda image, crop=None: live_nodes()
    monkeypatch.setattr(runner_mod.time, "sleep", lambda s: None)

    assert instance._step() is True
    assert backs["n"] == 1
    assert instance.escapes == 1
    assert len(instance.adb.taps) == 1  # 点了右上角关闭
    x, y = instance.adb.taps[0]
    assert x == int(W * instance.s.live_close_x) and y == int(H * instance.s.live_close_y)


def test_real_live_escape_skips_reward_logic(monkeypatch):
    """真按一次返回键后 _still_live 变 False，就只按一次。"""
    instance = make_runner(monkeypatch, decision=None)
    state = {"live": True, "back": 0}

    def back():
        state["back"] += 1
        state["live"] = False
        return True

    instance.adb.back = back
    instance.adb.current_focus = lambda: (
        "mCurrentFocus=Window{1 u0 com.luna.music/com.luna.biz.live.plugin.LunaDefaultLivePlayerActivity}"
        if state["live"]
        else "mCurrentFocus=Window{2 u0 com.luna.music/com.ss.android.excitingvideo.ExcitingVideoActivity}"
    )
    instance.ocr.nodes = lambda image, crop=None: live_nodes()
    monkeypatch.setattr(runner_mod.time, "sleep", lambda s: None)

    assert instance._step() is True
    assert state["back"] == 1


def test_escape_disabled_by_config(monkeypatch):
    instance = make_runner(monkeypatch, decision=None, live_room={"escape": False})
    instance.adb.back = lambda: (_ for _ in ()).throw(AssertionError("不该按返回键"))
    instance.ocr.nodes = lambda image, crop=None: live_nodes()
    assert instance._step() is False
    assert instance.escapes == 0


def test_not_live_activity_blocks_escape(monkeypatch):
    """画面像直播间但前台不是直播间 Activity -> 不按返回键（避免把 App 顶出去）。"""
    instance = make_runner(monkeypatch, decision=None)
    instance.adb.back = lambda: (_ for _ in ()).throw(AssertionError("不该按返回键"))
    instance.adb.current_focus = lambda: "mCurrentFocus=Window{3 u0 com.luna.music/com.luna.music.MainActivity}"
    instance.ocr.nodes = lambda image, crop=None: live_nodes()
    assert instance._step() is False
    assert instance.escapes == 0
