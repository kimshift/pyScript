# -*- coding: utf-8 -*-
"""全局热键适配层：用 pynput 替代已归档的 keyboard。

原实现是在循环里反复 `keyboard.is_pressed('f8')` 轮询；
现在改成「监听器回调置位标志 + 循环里读标志」，不再每轮询问系统。

注意：标志是**粘性**的——按一次 F8 后一直为 True，直到调用 `reset()`。
因此每个业务动作开始时调用一次 `hotkey.reset()`（见 __main__.py / emulator.py），
避免上一次的急停把下一次操作也直接掐掉。
"""

from __future__ import annotations

from kit.log import get_logger

log = get_logger(__name__)

DEFAULT_KEY = "f8"


class Hotkey:
    def __init__(self, key: str = DEFAULT_KEY):
        self.key_name = key.lower()
        self._stop = False
        self._listener = None

    # ---------- 生命周期 ----------

    def ensure_running(self) -> bool:
        """懒启动监听器；pynput 不可用时降级为「永不停止」并告警。"""
        if self._listener is not None:
            return True
        try:
            from pynput import keyboard

            target = getattr(keyboard.Key, self.key_name, None)
            if target is None:
                log.warning("pynput 不认识按键 %s，急停功能不可用", self.key_name)
                return False

            def on_press(key):
                if key == target:
                    self._stop = True
                    log.warning("检测到 %s，准备中断当前任务", self.key_name.upper())

            self._listener = keyboard.Listener(on_press=on_press)
            self._listener.daemon = True
            self._listener.start()
            log.debug("热键监听已启动：%s", self.key_name.upper())
            return True
        except Exception as exc:  # pynput 在无桌面/无权限环境会抛
            log.warning("热键监听启动失败（%s），急停功能不可用", exc)
            return False

    def stop(self) -> None:
        if self._listener is not None:
            try:
                self._listener.stop()
            finally:
                self._listener = None

    # ---------- 状态 ----------

    def should_stop(self) -> bool:
        """是否已请求中断（无副作用，可反复调用）。"""
        self.ensure_running()
        return self._stop

    def reset(self) -> None:
        """清除中断标志，供下一次业务动作使用。"""
        self._stop = False


hotkey = Hotkey()
