# -*- coding: utf-8 -*-
"""backends —— 外部程序/接口的封装层（CLI、adb 等），不含业务逻辑。"""

from tools.ld_emulator.backends.ldconsole import Instance, LdConsole, LdConsoleError

__all__ = ["Instance", "LdConsole", "LdConsoleError"]
