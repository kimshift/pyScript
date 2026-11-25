# -*- coding: utf-8 -*-
"""文字匹配与点击决策 —— 纯函数，不碰 adb / OCR，方便单测。

为什么单独一层
--------------
真机上的识别结果脏得很（`领取成功 ×`、`领収奖励`、`4s后进入直播间 [取消]`），
「识别到什么」和「该点哪儿」是两件事。把这层抽出来以后：
- 换了 OCR 引擎不影响点击策略；
- 不用连手机就能用单元测试覆盖优先级（tests/test_qishui_match.py）。

优先级（与参考实现一致，改之前先看 docs）
------------------------------------------
取消（拦截进入直播间） > 领取奖励/继续观看 > 领取成功/退出不看了 > 跳过
弹窗与广告结束页同时可见时先点「领取奖励」，不会误点背后的「领取成功」。
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# 「4s后 / 4秒后 / 4S后」这类倒计时（兼容全角 s）
COUNTDOWN_RE = re.compile(r"\d+\s*[秒sSｓＳ]\s*后")

# OCR 常见的形近字误识别（只做一对一替换，别写正则）
_OCR_FIXES = {
    "领収": "领取",
    "领职": "领取",
    "领敢": "领取",
    "领碼": "领取",
    "奨": "奖",
    "奬": "奖",
    "勵": "励",
}

# 末尾的 ×/括号/数字/标点一律剥掉：OCR 会把「领取成功 ×」读成一整段
_TRAILING_RE = re.compile(r"[×xX✕✖·•|丨\[\]【】()（）{}<>《》\d:：,，。.\-—_!！?？]+$")
_LEADING_RE = re.compile(r"^[×xX✕✖·•|丨\[\]【】()（）>》]+")
_SPACE_RE = re.compile(r"\s+")


@dataclass(frozen=True)
class Node:
    """屏幕上的一段文字及其位置（像素坐标，基于截图的真实分辨率）。"""

    label: str
    cx: int
    cy: int
    x1: int = 0
    y1: int = 0
    x2: int = 0
    y2: int = 0
    score: float = 1.0


@dataclass(frozen=True)
class Rule:
    """一条点击规则：命中 target 且落在 roi 内就点。

    action: reward / close / skip，仅用于统计与日志
    roi:    {"x": (x0, x1), "y": (y0, y1)}，0~1 相对坐标；None 表示全屏
    center: True 时在多个命中里取最靠近屏幕中心的（领奖按钮居中且最大），
            否则取「偏右上」的（关闭/跳过都在右上角）
    """

    action: str
    target: str
    roi: dict | None = None
    center: bool = False


@dataclass(frozen=True)
class Decision:
    """一次点击决策。dry_run 时只打印不执行。"""

    action: str
    target: str
    label: str
    x: int
    y: int
    reason: str = ""


# ------------------------- 文字归一化 / 匹配 -------------------------


def normalize_text(text: str) -> str:
    """去掉空白、末尾装饰符与数字，并修正常见形近字。"""
    if not text:
        return ""
    s = _SPACE_RE.sub("", str(text)).replace("\u3000", "")
    for bad, good in _OCR_FIXES.items():
        s = s.replace(bad, good)
    s = _TRAILING_RE.sub("", s)
    s = _LEADING_RE.sub("", s)
    return s


def text_match(recognized: str, target: str, fuzzy: bool = True) -> bool:
    """识别文本是否命中目标词。

    规则（从严到宽）：
    1. 完全相等，或目标词是识别结果的一部分（`领取成功 ×` 含 `领取成功`）；
    2. 识别结果只有 3 字以上时才允许反向包含（`广告` 不会命中 `关闭广告`）；
    3. fuzzy 时按「字命中数 ≥ 长度-1」兜底，接受 OCR 掉字。
    """
    a = normalize_text(recognized)
    b = normalize_text(target)
    if not a or not b:
        return False
    if a == b or b in a:
        return True
    if len(a) >= 3 and a in b:
        return True
    if not fuzzy:
        return False
    hit = sum(1 for ch in b if ch in a)
    return hit >= max(2, len(b) - 1)


# ------------------------- 区域过滤 -------------------------


def in_roi(node: Node, screen_w: int, screen_h: int, roi: dict | None) -> bool:
    """节点中心是否落在允许点击的区域内。roi 缺省 = 全屏。"""
    if not roi or not screen_w or not screen_h:
        return True
    (x0, x1), (y0, y1) = roi.get("x", (0.0, 1.0)), roi.get("y", (0.0, 1.0))
    return x0 * screen_w <= node.cx <= x1 * screen_w and y0 * screen_h <= node.cy <= y1 * screen_h


# ------------------------- 决策 -------------------------


def find_live_enter_cancel(nodes: list[Node], cancel_word: str = "取消", live_keyword: str = "进入直播间") -> Decision | None:
    """出现「4s后进入直播间 [取消]」时先点「取消」，别被自动带进直播间。

    普通横幅「点击进入直播间」不含倒计时，不会命中。
    """
    if not nodes:
        return None
    countdown = [n for n in nodes if COUNTDOWN_RE.search(n.label) and live_keyword in n.label]
    if not countdown:
        return None

    cancel = normalize_text(cancel_word)
    for node in nodes:  # 独立的「取消」节点，直接点中心
        if normalize_text(node.label) == cancel:
            return Decision("cancel", cancel_word, node.label, node.cx, node.cy, "倒计时进入直播间")

    for node in nodes:  # 兜底：OCR 把「倒计时 + 取消」并成一段，点该段右侧
        norm = normalize_text(node.label)
        if cancel in norm and len(norm) <= 12 and node.x2 > node.x1:
            x = int(node.x2 - (node.x2 - node.x1) * 0.12)
            return Decision("cancel", cancel_word, node.label, x, node.cy, "倒计时进入直播间（合并段）")
    return None


def decide(
    nodes: list[Node],
    screen_w: int,
    screen_h: int,
    rules: list[Rule],
    cancel_word: str = "取消",
    live_keyword: str = "进入直播间",
    fuzzy: bool = True,
) -> Decision | None:
    """按规则优先级返回第一个可点目标；没有可点的返回 None。"""
    if not nodes:
        return None

    cancel = find_live_enter_cancel(nodes, cancel_word, live_keyword)
    if cancel:
        return cancel

    for rule in rules:
        cands = [
            n
            for n in nodes
            if text_match(n.label, rule.target, fuzzy) and in_roi(n, screen_w, screen_h, rule.roi)
        ]
        if not cands:
            continue
        if rule.center:
            mid_x, mid_y = screen_w / 2, screen_h / 2
            best = min(cands, key=lambda n: (n.cx - mid_x) ** 2 + (n.cy - mid_y) ** 2)
        else:
            best = max(cands, key=lambda n: (n.cx, -n.cy))  # 越靠右、越靠上优先
        return Decision(rule.action, rule.target, best.label, best.cx, best.cy)
    return None
