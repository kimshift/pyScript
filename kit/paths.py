# -*- coding: utf-8 -*-
"""路径约定：所有脚本都从这里取路径，不要自己拼 ../..。

契约：
    REPO_ROOT/tools/<脚本名>/          每个脚本一个目录
    REPO_ROOT/tools/<脚本名>/config.json   该脚本自己的配置
    REPO_ROOT/tools/<脚本名>/assets/       该脚本自己的资源（图片/模板/数据）
    REPO_ROOT/kit/                     公共库（本模块所在位置）
"""

from pathlib import Path

# kit/paths.py -> kit/ -> 仓库根
REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = REPO_ROOT / "tools"


def tool_dir(name: str) -> Path:
    """返回 tools/<脚本名> 的绝对路径，不做存在性校验。"""
    return TOOLS_DIR / name


def ensure_tool_dir(name: str) -> Path:
    """返回 tools/<脚本名> 并确保目录存在。"""
    path = tool_dir(name)
    path.mkdir(parents=True, exist_ok=True)
    return path
