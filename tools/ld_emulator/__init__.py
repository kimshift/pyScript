# -*- coding: utf-8 -*-
"""ld_emulator —— 雷电模拟器（LDPlayer）批量自动化。

入口：python -m tools.ld_emulator <动作>
实现：见 emulator.Main.switch 的动作表。
"""

ACTIONS = [
    "create",        # 批量创建 → 配置 → 启动 → 装包 → 同步 → 权限 → 关同步
    "create_con",    # 已创建的情况下：装包 → 同步 → 权限 → 关同步（默认）
    "start",         # 启动所有已停止的模拟器
    "info",          # 列出实例（index/状态/分辨率/标题），只读
    "backup",        # 按 ID 范围备份
    "restore",       # 按 ID 范围还原
    "quitall",       # 关闭全部模拟器（CLI）
    "create_txt",    # 生成 cache.txt
    "default",       # 空动作，用于连通性自检
]

__all__ = ["ACTIONS"]
