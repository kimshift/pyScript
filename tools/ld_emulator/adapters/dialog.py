# -*- coding: utf-8 -*-
"""弹窗适配层：用标准库 tkinter.messagebox 替代 pyautogui 自带的 pymsgbox（Tk 封装）。

行为约定：
- confirm() 返回 True 表示用户选择了「确认/是」这一侧（api 与旧实现一致）；
- 若运行环境没有可用的显示（如服务/无桌面会话），降级为控制台询问；
  控制台也不可用时一律返回 False（保守：不执行破坏性操作）。
"""

from __future__ import annotations

import sys

from kit.log import get_logger

log = get_logger(__name__)


def _with_tk(show: str, *args, **kwargs):
    """在临时隐藏 Tk 窗口里调 messagebox.<show>(...)。

    tkinter 只在真正弹窗时才导入：无桌面会话的机器上 import 失败也能被调用方捕获降级。
    show 传方法名（"showinfo" / "askyesno"），避免把局部导入的名字漏到模块作用域。
    """
    import tkinter as tk
    from tkinter import messagebox

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    try:
        return getattr(messagebox, show)(*args, **kwargs)
    finally:
        root.destroy()


def alert(text: str, title: str = "提示") -> None:
    """信息提示框。"""
    message = str(text)
    log.info("弹窗提示：%s", message)
    try:
        _with_tk("showinfo", title, message)
    except Exception as exc:
        log.warning("弹窗不可用（%s），已退化为控制台输出", exc)
        print(f"[{title}] {message}")


def confirm(title: str = "标题", text: str = "内容", buttons: list[str] | None = None) -> bool:
    """确认框；返回 True 表示选择 buttons[1]（默认「确认」）。"""
    positive = (buttons or ["取消", "确认"])[-1]
    try:
        return bool(_with_tk("askyesno", title, f"{text}\n\n（选择“是”等于“{positive}”）"))
    except Exception as exc:
        log.warning("弹窗不可用（%s），降级为控制台询问", exc)

    if not sys.stdin or not sys.stdin.isatty():
        return False
    try:
        answer = input(f"[{title}] {text} —— 是否{positive}？(y/N) ").strip().lower()
        return answer in ("y", "yes")
    except (EOFError, KeyboardInterrupt):
        return False
