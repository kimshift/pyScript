# -*- coding: utf-8 -*-
"""点击决策的单元测试（纯逻辑，不需要手机/OCR）。

覆盖的是「识别结果脏数据 → 该点哪儿」这条路：归一化、模糊匹配、ROI 过滤、优先级。
真机行为靠 `python -m tools.qishui_auto check` 验证，两者互补。
"""

from tools.qishui_auto.config import from_dict
from tools.qishui_auto.match import (
    Decision,
    Node,
    Overlay,
    Rule,
    decide,
    in_roi,
    live_room_hints,
    normalize_text,
    overlay_hints,
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


def test_match_rejects_target_buried_in_sentence():
    """「完成互动，领取奖励福利」是标题，里面的「领取奖励」不是按钮，不能点。"""
    assert not text_match("完成互动，领取奖励福利", "领取奖励")
    assert not text_match("本活动领取奖励需完成3次互动", "领取奖励")
    # 按钮文字在一头的照旧命中（OCR 把前缀/后缀读进同一段是常见的）
    assert text_match("再领一次领取奖励", "领取奖励")
    assert text_match("领取奖励福利将于次日发放", "领取奖励")
    assert text_match("再看3个视频提前得第13日免费听领取奖励", "领取奖励")


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


def test_interaction_modal_clicks_button_not_title():
    """真机布局：标题「完成互动，领取奖励福利」在上，按钮「继续互动」在下。

    曾经把标题当成「领取奖励」点，导致一直卡在互动弹窗里出不来。
    """
    nodes = [
        node("15秒后可领取奖励×", 1096, 215),
        node("完成互动，领取奖励福利", 721, 1396, x1=334, x2=1108),
        node("继续互动", 720, 1632, x1=588, x2=852),
        node("坚持退出", 720, 1831),
    ]
    decision = decide(nodes, W, H, rules())
    assert decision.action == "reward"
    assert decision.target == "继续互动"
    assert (decision.x, decision.y) == (720, 1632)


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


def test_cancel_by_position_does_not_steal_reward():
    """倒计时胶囊在、但取消没读出来时，该点「领取奖励」而不是瞎猜位置。"""
    nodes = [
        node("6s后进入直播间", 628, 2221, x1=388, x2=868),
        node("领取奖励", 720, 1400),
    ]
    decision = decide(nodes, W, H, rules())
    assert decision.action == "reward"
    assert decision.target == "领取奖励"


def test_cancel_found_right_of_countdown_when_ocr_misreads():
    """OCR 常把「取消」读成「肖」这类单字，靠「倒计时右侧最右短文本」兜底。"""
    nodes = [
        node("6s后进入直播间", 628, 2221, x1=388, x2=868),
        node("肖", 1030, 2222, x1=1010, x2=1050),
    ]
    decision = decide(nodes, W, H, rules())
    assert decision.action == "cancel"
    assert decision.x == 1030  # 点到那个被读错的字上


def test_cancel_falls_back_to_position_when_text_missing():
    """连错字都没有时，仍要点胶囊右侧 —— 否则会被自动带进直播间卡死。"""
    nodes = [node("6s后进入直播间", 628, 2221, x1=388, x2=868)]
    decision = decide(nodes, W, H, rules())
    assert decision.action == "cancel"
    assert decision.x > 868  # 在胶囊右边
    assert decision.y == 2221


def test_cancel_fallback_ignores_far_away_text():
    """同一行但太远的文字（比如商品文案）不该被当成取消。"""
    nodes = [
        node("6s后进入直播间", 628, 2221, x1=388, x2=868),
        node("券后9.99", 1231, 3005, x1=1086, x2=1376),
    ]
    decision = decide(nodes, W, H, rules())
    assert decision.action == "cancel"
    assert 868 < decision.x < W * 0.9  # 位置兜底，不会跑去点右下角商品卡


# ------------------------- 规则展开 -------------------------


def test_rules_follow_priority_order():
    kinds = [rule.action for rule in rules()]
    assert kinds == ["reward", "reward", "reward", "close", "close", "skip", "skip", "skip"]


def test_rules_carry_roi_and_center():
    by_target = {rule.target: rule for rule in rules()}
    assert by_target["领取奖励"].center is True
    assert by_target["领取成功"].center is False
    assert by_target["跳过"].roi == {"x": [0.55, 1.0], "y": [0.0, 0.2]}


def test_rule_defaults_are_permissive():
    decision = decide([node("领取奖励", 540, 1200)], W, H, [Rule("reward", "领取奖励", None, True)])
    assert decision.target == "领取奖励"


# ------------------------- 覆盖层弹窗（优惠券之类） -------------------------


def coupon_nodes():
    """真机布局：橙色优惠券卡片，唯一文字按钮是「点击使用」，关闭是无字圆形 X。"""
    return [
        node("看了5秒，天降福利", 230, 177),
        node("恭喜获得满减券", 230, 418),
        node("46.01", 214, 508),
        node("点击使用", 230, 723),
        node("满92元可用", 230, 580),
    ]


def coupon_overlay():
    return Overlay("优惠券", ("天降福利", "点击使用", "满减券"), (0.5, 0.83), need=2, cooldown=5.0)


def test_overlay_closes_by_coordinate():
    decision = decide(coupon_nodes(), W, H, rules(), overlays=[coupon_overlay()])
    assert decision.action == "overlay"
    assert decision.target == "优惠券"
    assert (decision.x, decision.y) == (int(W * 0.5), int(H * 0.83))


def test_overlay_not_triggered_by_single_hint():
    nodes = [node("点击使用", 230, 723)]
    assert decide(nodes, W, H, rules(), overlays=[coupon_overlay()]) is None


def test_overlay_does_not_steal_real_button():
    """弹窗上若还有「领取奖励」这种真按钮，应先点它，不要按坐标乱点。"""
    nodes = coupon_nodes() + [node("领取奖励", 540, 1500)]
    decision = decide(nodes, W, H, rules(), overlays=[coupon_overlay()])
    assert decision.action == "reward"
    assert decision.target == "领取奖励"


def test_overlay_disabled_by_config():
    settings = from_dict({"overlays": [{"name": "优惠券", "hints": ["天降福利"], "enabled": False}]})
    assert settings.overlays == []


def test_overlay_without_hints_is_skipped():
    """配错（没写 hints）时静默跳过，别让主循环崩掉。"""
    settings = from_dict({"overlays": [{"name": "空", "hints": []}]})
    assert settings.overlays == []


def test_overlay_coordinates_are_clamped():
    settings = from_dict({"overlays": [{"name": "越界", "hints": ["天降福利"], "close_x": 3.0, "close_y": -1.0}]})
    assert settings.overlays[0].close == (1.0, 0.0)
