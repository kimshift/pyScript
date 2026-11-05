# -*- coding: utf-8 -*-
"""JSON 配置读写：统一 UTF-8、统一容错，避免每个脚本各写一套。"""

import json
from pathlib import Path


def read_json(path, default=None):
    """读取 JSON；文件不存在时返回 default（或空 dict），格式错误向上抛。"""
    p = Path(path)
    if not p.exists():
        return {} if default is None else default
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path, data, indent=4):
    """写入 JSON：UTF-8、不转义中文、末尾补换行（便于 git diff）。"""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=indent)
        f.write("\n")
