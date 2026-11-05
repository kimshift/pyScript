# -*- coding: utf-8 -*-
"""雷电模拟器批量自动化 —— 命令行入口。

用法：
    python -m tools.ld_emulator                        # 默认动作 create_con
    python -m tools.ld_emulator info                   # 列出实例（只读，不操作）
    python -m tools.ld_emulator create                 # 批量创建
    python -m tools.ld_emulator backup                 # 备份
    python -m tools.ld_emulator create --backend gui   # 强制走旧 GUI 流程

    mise run ld:create / ld:info / ld:check ...        # 推荐

后端：默认用雷电官方 ldconsole 命令行；同步器与模拟器内权限仍走 GUI。
注意：必须在仓库根目录执行（python -m 会把当前目录加入 sys.path），
或直接用 `mise run ...`（mise 会自动切到仓库根目录）。
"""

import sys

from kit.log import get_logger
from tools.ld_emulator.adapters import hotkey
from tools.ld_emulator.emulator import Main

DEFAULT_ACTION = "create_con"

log = get_logger("ld_emulator")


def _parse(argv: list[str]) -> tuple[list[str], str | None]:
    """拆出 --backend 参数，其余原样作为动作参数。"""
    backend = None
    if "--backend" in argv:
        i = argv.index("--backend")
        if i + 1 < len(argv):
            backend = argv[i + 1]
            del argv[i : i + 2]
        else:
            del argv[i]
    return argv, backend


def main(argv=None):
    argv, backend = _parse(list(sys.argv[1:] if argv is None else argv))
    action = argv[0] if argv else DEFAULT_ACTION

    hotkey.reset()  # 清掉上一次可能残留的 F8 中断标志
    log.info("动作：%s（后端：%s）", action, backend or "跟随配置")
    log.info("运行中可按 F8，或把鼠标移到屏幕左上角中断")
    Main(backend=backend).switch(action)


if __name__ == "__main__":
    main()
