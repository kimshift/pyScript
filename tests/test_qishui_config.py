# -*- coding: utf-8 -*-
"""配置层测试：默认值与 config/qishui.json 不许漂移，CLI 覆盖能生效。"""

import json

from kit.paths import config_path
from tools.qishui_auto.config import DEFAULTS, Settings, _uia_mode, from_dict


def _flatten(value, prefix=""):
    keys = set()
    for key, item in value.items():
        path = f"{prefix}{key}"
        if isinstance(item, dict):
            keys |= _flatten(item, path + ".")
        else:
            keys.add(path)
    return keys


def test_repo_config_matches_defaults():
    """仓库里的 qishui.json 必须能被 DEFAULTS 完整解释（防止加了新字段忘了同步）。"""
    raw = json.loads(config_path("qishui").read_text(encoding="utf-8"))
    missing = _flatten(raw) - _flatten(DEFAULTS)
    assert not missing, f"config/qishui.json 有 DEFAULTS 里没有的字段：{sorted(missing)}"


def test_missing_config_falls_back_to_defaults():
    settings = from_dict({})
    assert isinstance(settings, Settings)
    assert settings.reward_targets == DEFAULTS["targets"]["reward"]
    assert settings.dry_run is False
    assert settings.max_clicks == 0


def test_partial_override_keeps_siblings():
    settings = from_dict({"timing": {"click_cooldown": 1.5}, "targets": {"reward": ["领奖"]}})
    assert settings.click_cooldown == 1.5
    assert settings.poll_interval == DEFAULTS["timing"]["poll_interval"]
    assert settings.reward_targets == ["领奖"]
    assert settings.close_targets == DEFAULTS["targets"]["close"]


def test_uia_mode_normalization():
    assert _uia_mode(True) == "on"
    assert _uia_mode(False) == "off"
    assert _uia_mode("auto") == "auto"
    assert _uia_mode("乱写") == "auto"
    assert from_dict({"channels": {"uiautomator": False}}).uia_enabled is False


def test_small_ocr_width_is_clamped():
    """max_width < 600 会漏「取消」这类小字，加载时就抬到 600。"""
    assert from_dict({"ocr": {"max_width": 320}}).ocr_max_width == 600


def test_dry_run_flags_from_config():
    settings = from_dict({"dry_run": True, "max_clicks": 12, "mute_on_start": True})
    assert settings.dry_run is True
    assert settings.max_clicks == 12
    assert settings.mute_on_start is True
