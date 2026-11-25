# -*- coding: utf-8 -*-
"""uiautomator 兜底通道（默认关闭）。

能力边界（务必了解）
--------------------
- 只能读到**活动窗口**里的控件：广告结束页的「领取成功，关闭，按钮」能读到，
  但**奖励弹窗是覆盖层，读不到**；
- 视频广告播放期间永远等不到 idle，`uiautomator dump` 会卡到超时（本机约 11s）。

所以它只作为「OCR 本轮什么都没找到」时的兜底，且连续失败会自动关闭。
把它放在 OCR 前面会抢点「领取成功」，导致永远不去点「领取奖励」——这是参考实现
踩过的坑，别调换顺序。
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET

from tools.qishui_auto.adb import Adb
from tools.qishui_auto.match import Node

DUMP_PATH = "/sdcard/_qishui_dump.xml"
_BOUNDS_RE = re.compile(r"\[(-?\d+),(-?\d+)\]\[(-?\d+),(-?\d+)\]")


def dump_nodes(adb: Adb, timeout: int = 4) -> list[Node] | None:
    """导出控件树；失败返回 None（调用方据此判断通道是否可用）。"""
    adb.run(["shell", "rm", "-f", DUMP_PATH], timeout=timeout)
    if adb.run(["shell", "uiautomator", "dump", "--compressed", DUMP_PATH], timeout=timeout) is None:
        return None
    xml = adb.run(["shell", "cat", DUMP_PATH], timeout=timeout)
    adb.run(["shell", "rm", "-f", DUMP_PATH], timeout=timeout)
    if not xml or "<hierarchy" not in xml:
        return None

    start = xml.find("<hierarchy")
    end = xml.rfind(">")
    if start < 0 or end <= start:
        return None
    try:
        root = ET.fromstring(xml[start : end + 1])
    except ET.ParseError:
        return None

    nodes: list[Node] = []
    for item in root.iter("node"):
        label = (item.get("text") or "").strip() or (item.get("content-desc") or "").strip()
        if not label:
            continue
        match = _BOUNDS_RE.match(item.get("bounds") or "")
        if not match:
            continue
        x1, y1, x2, y2 = (int(v) for v in match.groups())
        if x2 <= x1 or y2 <= y1:
            continue
        nodes.append(
            Node(
                label=label,
                cx=(x1 + x2) // 2,
                cy=(y1 + y2) // 2,
                x1=x1,
                y1=y1,
                x2=x2,
                y2=y2,
            )
        )
    return nodes


class UiaChannel:
    """带探测与自动降级的 uiautomator 会话。"""

    def __init__(self, adb: Adb, mode: str = "auto", timeout: int = 4, max_fail: int = 3, log=None):
        self.adb = adb
        self.mode = mode  # auto / on / off
        self.timeout = timeout
        self.max_fail = max_fail
        self.fails = 0
        self.usable: bool | None = False if mode == "off" else None
        self._log = log or (lambda *a, **k: None)

    def probe(self) -> bool:
        """只在 auto 模式下探测一次，结果本次会话沿用。"""
        if self.mode == "off":
            self.usable = False
            return False
        if self.mode == "on":
            self.usable = True
            return True
        if self.usable is not None:
            return self.usable
        self.usable = dump_nodes(self.adb, timeout=self.timeout) is not None
        return self.usable

    def nodes(self) -> list[Node] | None:
        """取一次控件树；连续失败超过阈值就永久关闭本会话。"""
        if not self.usable:
            return None
        result = dump_nodes(self.adb, timeout=self.timeout)
        if result is None:
            self.fails += 1
            if self.fails >= self.max_fail:
                self.usable = False
                self._log("uiautomator 连续失败 %d 次，本次会话关闭该通道", self.fails)
            return None
        self.fails = 0
        return result
