# -*- coding: utf-8 -*-
"""汽水音乐自动看广告 —— 纯 UI 自动化（ADB 截图 + OCR 识别 + 点击）。

只点击界面上真实存在的按钮：不修改 App、不伪造广告进度、不加速播放。
广告该播多久还是多久，脚本只负责替你点「领取奖励 / 领取成功 × / 跳过」。
"""

ACTIONS = ("run", "check", "devices", "wifi")

ACTION_TEXT = {
    "run": "开始自动看广告（默认）",
    "check": "自检：adb / 设备 / 分辨率 / OCR / 当前屏幕能识别到什么（不点击）",
    "devices": "列出 adb 在线设备（只读）",
    "wifi": "无线调试：配对 / 连接手机，之后不用插数据线",
}

__all__ = ["ACTIONS", "ACTION_TEXT"]
