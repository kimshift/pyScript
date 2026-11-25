# -*- coding: utf-8 -*-
"""点击决策的单元测试（纯逻辑，不需要手机/OCR）。

覆盖的是「识别结果脏数据 → 该点哪儿」这条路：归一化、模糊匹配、ROI 过滤、优先级。
真机行为靠 `python -m tools.qishui_auto check` 验证，两者互补。
"""

from tools.qishui_auto.config import from_dict
from tools.qishui_auto.match import (
    Decision,
    Node,
    Rule,
    decide,
    in_roi,
    normalize_text,
    text_match,
)

W, H = 1080, 2400


def node(label, cx, cy, x1=None, y1=None, x2=None, y2=None):
    return Node(
        label=label,
        cx=cx,
        cy=cy,
        x1=cx - 40 if x1 is None else x1,
        y1=cy - 20 if y1 is None else y1,
        x2=cx + 40 if x2 is None else x2,
        y2=cy + 20 if y2 is None else y2,
    )


def rules(**kwargs):
    return from_dict(kwargs).rules


# ------------------------- 归一化 -------------------------


def test_normalize_strips_decorations():
    assert normalize_text("领取成功 ×") == "领取成功"
    assert normalize_text("【领取奖励】") == "领取奖励"
    assert normalize_text("跳过 5") == "跳过"
    assert normalize_text("  领取　奖励 ") == "领取奖励"


def test_normalize_fixes_common_ocr_errors():
    assert normalize_text("领収奖励") == "领取奖励"
    assert normalize_text("奨励") == "奖励"


# ------------------------- 匹配 -------------------------


def test_match_accepts_capsule_label():
    assert text_match("领取成功 ×", "领取成功")
    assert text_match("领取成功，关闭，按钮", "领取成功")


def test_match_rejects_short_false_positive():
    # 「广告」不能命中「关闭广告」：识别结果少于 3 字时不允许反向包含
    assert not text_match("广告", "关闭广告")


def test_match_does_not_confuse_reward_and_close():
    assert not text_match("领取奖励", "领取成功")
    assert not text_match("领取成功", "领取奖励")


def test_match_can_be_strict():
    assert text_match("领取奖励", "领取奖励", fuzzy=False)
    # 3 字以上允许反向包含（OCR 掉字），2 字不行：严格模式就是用来挡这种的
    assert text_match("领取奖", "领取奖励", fuzzy=False)
    assert not text_match("领取", "领取奖励", fuzzy=False)


# ------------------------- ROI -------------------------


def test_in_roi_bounds():
    roi = {"x": [0.2, 0.8], "y": [0.3, 0.78]}
    assert in_roi(node("领取奖励", 540, 1500), W, H, roi)
    assert not in_roi(node("领取奖励", 100, 2200), W, H, roi)
    assert in_roi(node("任意", 10, 10), W, H, None)


# ------------------------- 决策优先级 -------------------------


def test_reward_wins_over_close_when_both_visible():
    """弹窗与广告结束页同时可见时，必须先点「领取奖励」。"""
    nodes = [
        node("领取成功 ×", 900, 120),
        node("领取奖励", 540, 1500),
    ]
    decision = decide(nodes, W, H, rules())
    assert isinstance(decision, Decision)
    assert decision.action == "reward"
    assert decision.target == "领取奖励"


def test_reward_wins_over_skip():
    nodes = [node("跳过", 950, 100), node("继续观看", 540, 1400)]
    decision = decide(nodes, W, H, rules())
    assert decision.action == "reward"
    assert decision.target == "继续观看"


def test_close_used_when_no_reward():
    nodes = [node("领取成功 ×", 900, 120)]
    decision = decide(nodes, W, H, rules())
    assert decision.action == "close"
    assert (decision.x, decision.y) == (900, 120)


def test_skip_can_be_disabled():
    nodes = [node("跳过", 950, 100)]
    assert decide(nodes, W, H, rules()) is not None
    assert decide(nodes, W, H, rules(enable_skip=False)) is None


def test_center_target_prefers_closest_to_center():
    nodes = [
        node("领取奖励", 300, 900),
        node("领取奖励", 545, 1510),
    ]
    decision = decide(nodes, W, H, rules())
    assert (decision.x, decision.y) == (545, 1510)


def test_roi_filters_out_wrong_place():
    # 奖励按钮跑到屏幕底部（超出 ROI），不该点
    nodes = [node("领取奖励", 540, 2300)]
    assert decide(nodes, W, H, rules()) is None


def test_nothing_clickable_returns_none():
    assert decide([], W, H, rules()) is None
    assert decide([node("广告剩余 15 秒", 540, 200)], W, H, rules()) is None


# ------------------------- 直播拦截 -------------------------


def test_cancel_live_enter_by_separate_cancel_node():
    nodes = [
        node("4s后进入直播间", 500, 1200),
        node("取消", 880, 1240),
    ]
    decision = decide(nodes, W, H, rules())
    assert decision.action == "cancel"
    assert (decision.x, decision.y) == (880, 1240)


def test_cancel_live_enter_by_merged_segment():
    nodes = [node("4s后进入直播间 取消", 700, 1200, x1=400, x2=1000)]
    decision = decide(nodes, W, H, rules())
    assert decision.action == "cancel"
    assert decision.x > 900  # 点在合并段右侧


def test_plain_banner_does_not_trigger_cancel():
    nodes = [node("点击进入直播间", 540, 1800), node("领取奖励", 540, 1500)]
    decision = decide(nodes, W, H, rules())
    assert decision.action == "reward"


def test_cancel_has_top_priority():
    nodes = [
        node("领取奖励", 540, 1500),
        node("4s后进入直播间", 500, 1200),
        node("取消", 880, 1240),
    ]
    assert decide(nodes, W, H, rules()).action == "cancel"


# ------------------------- 规则展开 -------------------------


def test_rules_follow_priority_order():
    kinds = [rule.action for rule in rules()]
    assert kinds == ["reward", "reward", "close", "close", "skip", "skip", "skip"]


def test_rules_carry_roi_and_center():
    by_target = {rule.target: rule for rule in rules()}
    assert by_target["领取奖励"].center is True
    assert by_target["领取成功"].center is False
    assert by_target["跳过"].roi == {"x": [0.55, 1.0], "y": [0.0, 0.2]}


def test_rule_defaults_are_permissive():
    decision = decide([node("领取奖励", 540, 1200)], W, H, [Rule("reward", "领取奖励", None, True)])
    assert decision.target == "领取奖励"
