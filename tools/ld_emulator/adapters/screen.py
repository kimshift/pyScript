# -*- coding: utf-8 -*-
"""截图适配层：用 mss 替代 pyautogui.screenshot。

为什么换：
- pyautogui 0.9.54 已停更，且截图走 PIL，全屏 1920x1080 约 60ms；
- mss 直接调 BitBlt，支持指定区域，便于后续做 ROI 优化。

通道顺序：mss 返回 BGRA，转灰度用 COLOR_BGRA2GRAY，
与原实现（PIL RGB -> COLOR_RGB2GRAY）等价，模板匹配置信度不应有肉眼可见变化。
"""

from __future__ import annotations

import numpy as np

from kit.log import get_logger

log = get_logger(__name__)


class Screen:
    """屏幕截图器。mss 实例不能跨线程复用，这里按单线程使用。"""

    def __init__(self):
        self._sct = None
        self._cv2 = None

    def _env(self):
        if self._sct is None:
            import mss

            self._sct = mss.mss()
        if self._cv2 is None:
            import cv2

            self._cv2 = cv2
        return self._sct, self._cv2

    def size(self) -> tuple[int, int]:
        sct, _ = self._env()
        monitor = sct.monitors[1]
        return monitor["width"], monitor["height"]

    def grab_gray(self, region: tuple[int, int, int, int] | None = None) -> np.ndarray:
        """截屏并直接返回灰度 ndarray（H, W）。

        region = (left, top, width, height)，None 表示整个主屏。
        """
        sct, cv2 = self._env()
        if region:
            left, top, width, height = region
            monitor = {"left": left, "top": top, "width": width, "height": height}
        else:
            monitor = sct.monitors[1]
        frame = np.asarray(sct.grab(monitor))  # BGRA
        return cv2.cvtColor(frame, cv2.COLOR_BGRA2GRAY)

    def grab_bgr(self, region: tuple[int, int, int, int] | None = None) -> np.ndarray:
        """截屏并返回 BGR ndarray（H, W, 3），与 cv2.imread 通道一致。"""
        sct, cv2 = self._env()
        if region:
            left, top, width, height = region
            monitor = {"left": left, "top": top, "width": width, "height": height}
        else:
            monitor = sct.monitors[1]
        frame = np.asarray(sct.grab(monitor))
        return cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)

    def close(self) -> None:
        if self._sct is not None:
            self._sct.close()
            self._sct = None


# 全局单例：避免每次截图都重建 mss 上下文
screen = Screen()
