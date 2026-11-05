# -*- coding: utf-8 -*-
"""新脚本脚手架：在 tools/ 下生成一个可运行的最小脚本骨架。

用法（仓库根目录）：
    python scripts/new_tool.py json_cleaner

生成：
    tools/json_cleaner/__init__.py
    tools/json_cleaner/__main__.py
    tools/json_cleaner/README.md
    tools/json_cleaner/assets/.gitkeep

之后按需：
    1) 依赖写进 pyproject.toml 的 [project.optional-dependencies]（新组或复用已有组）
    2) mise.toml 里加一个 task，例如：
         [tasks."json:run"]
         run = "uv run --extra json python -m tools.json_cleaner"
    3) 运行：mise run json:run
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = REPO_ROOT / "tools"

INIT_PY = '''# -*- coding: utf-8 -*-
"""{name} —— 一句话说明这个脚本做什么。"""

__all__ = []
'''

MAIN_PY = '''# -*- coding: utf-8 -*-
"""{name} —— 命令行入口。

用法：
    python -m tools.{name}
    mise run {name}      # 在 mise.toml 里配好 task 之后
"""

import sys

from kit.log import get_logger

log = get_logger("{name}")


def run(argv: list[str]) -> int:
    log.info("参数：%s", argv)
    # TODO: 在这里写你的逻辑
    return 0


def main(argv=None) -> int:
    return run(sys.argv[1:] if argv is None else list(argv))


if __name__ == "__main__":
    raise SystemExit(main())
'''

README_MD = '''# {name}

一句话说明这个脚本做什么。

## 运行

```sh
mise run setup                      # 首次：装依赖
uv run python -m tools.{name}
```

## 依赖

在根目录 `pyproject.toml` 的 `[project.optional-dependencies]` 里登记，
优先复用已有分组，避免重复声明。

## 配置 / 资源 / 日志

- 配置：`config/{name}.json`（统一放仓库根目录；代码里用 `kit.paths.config_path("{name}")` 定位）
  - 本机私有值放 `config/{name}.local.json`（已 gitignore），**不要**写进公共配置
- 资源：`tools/{name}/assets/`
- 日志：`logs/{name}/`（统一放仓库根目录；代码里用 `kit.paths.log_dir("{name}")` 定位）
'''

GITKEEP = ""


def scaffold(name: str) -> int:
    if not name.isidentifier():
        print(f"脚本名必须是合法的 Python 标识符（字母/数字/下划线）：{name}")
        return 1

    target = TOOLS_DIR / name
    if target.exists():
        print(f"已存在，未覆盖：{target}")
        return 1

    (target / "assets").mkdir(parents=True)
    (target / "__init__.py").write_text(INIT_PY.format(name=name), encoding="utf-8")
    (target / "__main__.py").write_text(MAIN_PY.format(name=name), encoding="utf-8")
    (target / "README.md").write_text(README_MD.format(name=name), encoding="utf-8")
    (target / "assets" / ".gitkeep").write_text(GITKEEP, encoding="utf-8")

    print(f"已生成：tools/{name}/")
    print("下一步：")
    print("  1) 依赖登记到 pyproject.toml 的 [project.optional-dependencies]")
    print(f"  2) mise.toml 增加 task：uv run --extra <组名> python -m tools.{name}")
    print(f"  3) 运行：uv run python -m tools.{name}")
    return 0


def main(argv) -> int:
    if len(argv) != 1 or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0 if argv and argv[0] in ("-h", "--help") else 1
    return scaffold(argv[0])


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
