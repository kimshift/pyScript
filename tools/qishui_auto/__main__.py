# -*- coding: utf-8 -*-
"""汽水音乐自动看广告 —— 命令行入口。

用法（仓库根目录执行）：
    python -m tools.qishui_auto                    # 默认 run：开始自动看广告
    python -m tools.qishui_auto run --dry-run      # 只识别不点击，先确认它会点哪儿
    python -m tools.qishui_auto check              # 自检：adb / 设备 / 分辨率 / OCR / 当前屏幕
    python -m tools.qishui_auto devices            # 列出 adb 在线设备（只读）

    mise run qs:run / qs:dry / qs:check / qs:devices

退出码：0 成功｜1 参数或配置错误｜2 运行失败（无 adb / 设备离线 / OCR 不可用）
"""

import sys


def _utf8_console() -> None:
    """Windows 控制台默认 GBK，统一成 UTF-8 再输出，免得日志里中文报错。"""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError, OSError):
            pass


def main(argv=None) -> int:
    _utf8_console()
    from tools.qishui_auto.runner import main as run

    return run(sys.argv[1:] if argv is None else list(argv))


if __name__ == "__main__":
    raise SystemExit(main())
