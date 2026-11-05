# -*- coding: utf-8 -*-
"""adapters —— 把「停更的底层库」隔离在这一层，业务代码不直接依赖它们。

替换关系（见 docs/依赖重构清单.md）：
    截图        pyautogui.screenshot  ->  adapters.screen  (mss)
    热键监听    keyboard.is_pressed   ->  adapters.hotkey  (pynput)
    弹窗        pyautogui.alert       ->  adapters.dialog  (tkinter)

以后要再换实现（比如截图换 DXGI），只改这里，不动 common.py / emulator.py。
"""

from tools.ld_emulator.adapters.dialog import alert, confirm
from tools.ld_emulator.adapters.hotkey import hotkey
from tools.ld_emulator.adapters.screen import screen

__all__ = ["alert", "confirm", "hotkey", "screen"]
