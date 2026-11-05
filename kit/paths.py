# -*- coding: utf-8 -*-
"""路径约定：所有脚本都从这里取路径，不要自己拼 ../..。

契约：
    REPO_ROOT/tools/<脚本名>/               每个脚本一个目录（只放代码/资源）
    REPO_ROOT/tools/<脚本名>/assets/        该脚本自己的资源（图片/模板/数据）
    REPO_ROOT/config/<脚本名>.json          该脚本自己的配置（不含本机绝对路径）
    REPO_ROOT/config/<脚本名>.local.json    本机私有覆盖（已 gitignore，可选）
    REPO_ROOT/logs/<脚本名>/                该脚本的运行日志（统一放根目录，便于集中查看）
    REPO_ROOT/kit/                          公共库（本模块所在位置）

配置与日志为什么都放根目录
--------------------------
两者都是「每个脚本一份、但要集中看」的东西：
- 配置：新电脑拉下来只需进一个 config/ 目录就能把所有路径填完，不用挨个翻 tools/；
- 日志：排查时只看一个地方，清理/打包/加 .gitignore 都是同一条规则。
"""

from pathlib import Path

# kit/paths.py -> kit/ -> 仓库根
REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = REPO_ROOT / "tools"
CONFIG_DIR = REPO_ROOT / "config"
LOGS_DIR = REPO_ROOT / "logs"


def tool_dir(name: str) -> Path:
    """返回 tools/<脚本名> 的绝对路径，不做存在性校验。"""
    return TOOLS_DIR / name


def ensure_tool_dir(name: str) -> Path:
    """返回 tools/<脚本名> 并确保目录存在。"""
    path = tool_dir(name)
    path.mkdir(parents=True, exist_ok=True)
    return path


def config_path(name: str) -> Path:
    """返回 config/<脚本名>.json 的绝对路径，不做存在性校验。

    机器私有覆盖由 kit.config.load_config() 自动找同目录的
    <脚本名>.local.json，调用方不需要关心。
    """
    return CONFIG_DIR / f"{name}.json"


def log_dir(name: str, create: bool = False) -> Path:
    """返回 logs/<脚本名>/ 的绝对路径。

    create=True 时顺带建目录（写日志前调用一次即可）。
    """
    path = LOGS_DIR / name
    if create:
        path.mkdir(parents=True, exist_ok=True)
    return path
