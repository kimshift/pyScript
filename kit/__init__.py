# -*- coding: utf-8 -*-
"""kit —— 跨脚本公共库。

原则：这里只放**与业务无关**、可被任意脚本复用的小能力。
业务逻辑一律留在 tools/<脚本名>/ 里，不要往 kit 塞。
"""

from kit.paths import REPO_ROOT, TOOLS_DIR, tool_dir

__all__ = ["REPO_ROOT", "TOOLS_DIR", "tool_dir"]
