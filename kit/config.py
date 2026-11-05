# -*- coding: utf-8 -*-
"""JSON 配置读写：统一 UTF-8、统一容错，避免每个脚本各写一套。

机器私有配置（重要）
--------------------
    config/<脚本名>.json          入库的公共配置，**不允许**写本机绝对路径
    config/<脚本名>.local.json    机器私有覆盖，已 gitignore，存在才叠加

全部脚本的配置都集中在仓库根 config/ 下：新电脑拉下来进一个目录就能填完。
同一个键在 local 里出现就覆盖公共配置，所以「雷电装在哪」这类信息
留在各自电脑上，不会被推到远端仓库。
"""

import json
import os
from pathlib import Path

# <脚本名>.json -> <脚本名>.local.json
LOCAL_SUFFIX = ".local"


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


def local_config_path(base_path):
    """config/<名>.json -> 同目录的 config/<名>.local.json。"""
    p = Path(base_path)
    return p.with_name(p.stem + LOCAL_SUFFIX + p.suffix)


def _merge(base, override):
    """把 override 递归合并进 base（就地修改并返回）。"""
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _merge(base[key], value)
        else:
            base[key] = value
    return base


def load_config(base_path, default=None):
    """读 base_path，再叠加同目录的 <名>.local.json（存在才叠）。

    先读公共配置，再让机器私有配置覆盖 -> 仓库里永远是通用值，
    本机的真实路径只存在于被忽略的 local 文件里。
    """
    cfg = read_json(base_path, default=default)
    local = local_config_path(base_path)
    if local.is_file():
        _merge(cfg, read_json(local))
    return cfg


def expand_path(value, base=None):
    """展开 ~、%VAR%、$VAR，并把相对路径挂到 base 下。

    空值返回 None，调用方据此走自动探测或给出提示。
    """
    if not value:
        return None
    path = Path(os.path.expandvars(os.path.expanduser(str(value))))
    if base is not None and not path.is_absolute():
        path = Path(base) / path
    return path
