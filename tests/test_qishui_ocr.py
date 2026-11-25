# -*- coding: utf-8 -*-
"""OCR 主通道的集成测试：合成截图 → 真实 OCR → 点击决策。

不连手机也能覆盖最容易出问题的一段：图片解码、缩放还原、坐标换算、中文识别。
没有 cv2 / rapidocr / 中文字体的机器上自动跳过（不影响 CI）。
"""

from pathlib import Path

import pytest

pytest.importorskip("cv2")
pytest.importorskip("PIL")
pytest.importorskip("numpy")

from tools.qishui_auto.config import from_dict
from tools.qishui_auto.match import decide
from tools.qishui_auto.ocr import OcrEngine

W, H = 1080, 2400

_FONT_CANDIDATES = (
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/msyhbd.ttc",
    "/System/Library/Fonts/PingFang.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
)


def _font_path() -> str | None:
    return next((p for p in _FONT_CANDIDATES if Path(p).is_file()), None)


pytestmark = [
    pytest.mark.skipif(_font_path() is None, reason="没有可用的中文字体，跳过合成截图测试"),
    pytest.mark.skipif(not OcrEngine.deps_status()[0], reason="OCR 依赖未安装（mise run qs:setup）"),
]


@pytest.fixture(scope="module")
def engine() -> OcrEngine:
    return OcrEngine(min_score=0.5, max_width=720, use_cls=False)


def render(items):
    """按 (文字, 左上角坐标, 字号) 画一张 1080x2400 的模拟截图。"""
    import cv2
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont

    image = Image.new("RGB", (W, H), (18, 18, 20))
    draw = ImageDraw.Draw(image)
    font_path = _font_path()
    for text, xy, size in items:
        draw.text(xy, text, font=ImageFont.truetype(font_path, size), fill=(255, 255, 255))
    return cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)


def click(nodes):
    return decide(nodes, W, H, from_dict({}).rules, "取消", "进入直播间", True)


def test_reward_popup_is_clicked(engine):
    nodes = engine.nodes(
        render(
            [
                ("再看1个视频得今日免费听", (150, 900), 52),
                ("领取奖励", (390, 1440), 66),
                ("放弃", (470, 1620), 44),
            ]
        )
    )
    decision = click(nodes)
    assert decision is not None
    assert decision.action == "reward"
    assert decision.target == "领取奖励"
    # 坐标必须落在原图分辨率内，且贴近按钮中心（缩放还原没错位）
    assert abs(decision.x - 520) < 60 and abs(decision.y - 1490) < 60


def test_ad_end_page_closes_before_skipping(engine):
    """「领取成功 ×」与「跳过」同时可见时，先关广告而不是跳过。"""
    nodes = engine.nodes(
        render(
            [
                ("15秒后可领取奖励", (300, 120), 46),
                ("领取成功 ×", (780, 120), 48),
                ("跳过 5", (860, 260), 44),
            ]
        )
    )
    decision = click(nodes)
    assert decision is not None
    assert decision.action == "close"
    assert decision.target == "领取成功"


def test_live_enter_countdown_is_cancelled(engine):
    nodes = engine.nodes(render([("4s后进入直播间", (240, 1150), 48), ("取消", (820, 1150), 48)]))
    decision = click(nodes)
    assert decision is not None
    assert decision.action == "cancel"


def test_empty_screen_has_no_decision(engine):
    assert click(engine.nodes(render([("正在播放", (400, 1200), 48)]))) is None


def test_crop_keeps_absolute_coordinates(engine):
    """裁剪后坐标必须还原成整屏坐标，否则会点错位置。"""
    image = render([("领取奖励", (390, 1440), 66)])
    full = engine.nodes(image)
    cut = engine.nodes(image, (0.0, 0.9))
    full_node = next(n for n in full if "领取奖励" in n.label)
    cut_node = next(n for n in cut if "领取奖励" in n.label)
    assert abs(cut_node.cx - full_node.cx) <= 12
    assert abs(cut_node.cy - full_node.cy) <= 12


def test_crop_excludes_band_below_limit(engine):
    """裁剪区（scan_bottom）以下的文字不该被识别，这正是省时间的来源。"""
    image = render([("商品福利区文字", (400, 2100), 56)])
    assert any("商品" in n.label for n in engine.nodes(image))
    cut = engine.nodes(image, (0.0, 0.85))
    assert not any("商品" in n.label for n in cut)


def test_crop_result_matches_full_screen_decision(engine):
    """真实布局：裁剪后仍应点同一个按钮。"""
    image = render(
        [
            ("15秒后可领取奖励", (300, 120), 46),
            ("完成互动，领取奖励福利", (330, 1360), 52),
            ("继续互动", (588, 1596), 66),
            ("坚持退出", (604, 1798), 44),
        ]
    )
    full_decision = click(engine.nodes(image))
    cut_decision = click(engine.nodes(image, (0.0, 0.9)))
    assert full_decision is not None and cut_decision is not None
    assert full_decision.target == cut_decision.target == "继续互动"
