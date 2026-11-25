# -*- coding: utf-8 -*-
"""调试图清理的单元测试：不连手机、不跑 OCR，只验证磁盘文件的增删规则。

一张标注截图 1~4MB，长时间跑会攒到几个 GB，所以清理规则必须可测：
- 启动清空（默认全清，可留最新几张）；
- 运行中按「总量」而不是「张数」压上限；
- 只删图片，别误伤目录里的其他文件。
"""

import os
import time

from tests.test_qishui_runner import make_runner
from tools.qishui_auto.config import from_dict
from tools.qishui_auto.ocr import clear_debug_images, trim_debug_images


def make_files(root, sizes, prefix="shot"):
    """按给定大小造文件，并把 mtime 依次调开（保证「最旧」判断稳定）。"""
    root.mkdir(parents=True, exist_ok=True)
    paths = []
    base = time.time() - 10_000
    for index, size in enumerate(sizes):
        path = root / f"{prefix}_{index:03d}.png"
        path.write_bytes(b"\x00" * size)
        stamp = base + index
        os.utime(path, (stamp, stamp))
        paths.append(path)
    return paths


def test_clear_removes_everything_by_default(tmp_path):
    make_files(tmp_path, [10, 20, 30])
    assert clear_debug_images(tmp_path, keep=0) == 3
    assert list(tmp_path.iterdir()) == []


def test_clear_keeps_newest_when_asked(tmp_path):
    paths = make_files(tmp_path, [10, 20, 30, 40])
    assert clear_debug_images(tmp_path, keep=2) == 2
    left = sorted(p.name for p in tmp_path.iterdir())
    assert left == [paths[2].name, paths[3].name]  # 最新的两张


def test_clear_ignores_non_image_files(tmp_path):
    """目录里可能有手写的说明/备份，不能一起删掉。"""
    make_files(tmp_path, [10])
    note = tmp_path / "说明.txt"
    note.write_text("别删我", encoding="utf-8")
    assert clear_debug_images(tmp_path, keep=0) == 1
    assert note.is_file()


def test_clear_on_missing_dir_is_noop(tmp_path):
    assert clear_debug_images(tmp_path / "不存在", keep=0) == 0


def test_trim_drops_oldest_until_under_limit(tmp_path):
    # 4 张各 1MB，上限 2.5MB -> 应该删掉最旧的 2 张
    paths = make_files(tmp_path, [1024 * 1024] * 4)
    removed = trim_debug_images(tmp_path, max_total_mb=2.5)
    assert removed == 2
    assert sorted(p.name for p in tmp_path.iterdir()) == [paths[2].name, paths[3].name]


def test_trim_does_nothing_below_limit(tmp_path):
    make_files(tmp_path, [1024] * 3)
    assert trim_debug_images(tmp_path, max_total_mb=512) == 0


def test_trim_disabled_by_zero(tmp_path):
    make_files(tmp_path, [1024] * 5)
    assert trim_debug_images(tmp_path, max_total_mb=0) == 0
    assert len(list(tmp_path.iterdir())) == 5


# ------------------------- 配置 -------------------------


def test_debug_cleanup_defaults():
    settings = from_dict({})
    assert settings.clear_on_start is True  # 默认开：不然会越攒越多
    assert settings.keep_files == 0
    assert settings.max_total_mb == 512
    assert settings.debug_trim_every == 50


def test_debug_cleanup_can_be_tuned():
    settings = from_dict({"debug": {"clear_on_start": False, "keep_files": 5, "max_total_mb": 64, "trim_every": 10}})
    assert settings.clear_on_start is False
    assert settings.keep_files == 5
    assert settings.max_total_mb == 64
    assert settings.debug_trim_every == 10


def test_debug_trim_every_never_zero():
    """0 会让 `seq % 0` 抛异常，配置层就兜到 1。"""
    assert from_dict({"debug": {"trim_every": 0}}).debug_trim_every == 1


# ------------------------- 与主循环的接线 -------------------------


def test_prepare_clears_previous_run_shots(monkeypatch, tmp_path):
    """开跑前把上一轮截图清掉，避免一张 1~4MB 的图越攒越多。"""
    make_files(tmp_path, [1024] * 3)
    instance = make_runner(monkeypatch, debug={"save_click_images": True, "clear_on_start": True})
    monkeypatch.setattr(type(instance.s), "debug_dir", property(lambda self: tmp_path))

    instance._prepare_debug_dir()
    assert list(tmp_path.iterdir()) == []


def test_prepare_respects_keep_files(monkeypatch, tmp_path):
    paths = make_files(tmp_path, [1024] * 3)
    instance = make_runner(monkeypatch, debug={"save_click_images": True, "keep_files": 1})
    monkeypatch.setattr(type(instance.s), "debug_dir", property(lambda self: tmp_path))

    instance._prepare_debug_dir()
    assert [p.name for p in tmp_path.iterdir()] == [paths[-1].name]


def test_prepare_skipped_when_images_disabled(monkeypatch, tmp_path):
    make_files(tmp_path, [1024])
    instance = make_runner(monkeypatch, debug={"save_click_images": False})
    monkeypatch.setattr(type(instance.s), "debug_dir", property(lambda self: tmp_path))

    instance._prepare_debug_dir()
    assert len(list(tmp_path.iterdir())) == 1  # 没开截图就不该动目录


def test_prepare_skipped_in_dry_run(monkeypatch, tmp_path):
    make_files(tmp_path, [1024])
    instance = make_runner(monkeypatch, dry_run=True, debug={"save_click_images": True})
    monkeypatch.setattr(type(instance.s), "debug_dir", property(lambda self: tmp_path))

    instance._prepare_debug_dir()
    assert len(list(tmp_path.iterdir())) == 1


def test_trim_runs_every_n_files(monkeypatch, tmp_path):
    make_files(tmp_path, [1024 * 1024] * 4)
    instance = make_runner(
        monkeypatch,
        debug={"save_click_images": True, "max_total_mb": 2.5, "trim_every": 5},
    )
    monkeypatch.setattr(type(instance.s), "debug_dir", property(lambda self: tmp_path))

    instance._debug_written = 4  # 还没到第 5 张
    instance._trim_debug_if_needed()
    assert len(list(tmp_path.iterdir())) == 4

    instance._debug_written = 5  # 到点，压回 2 张
    instance._trim_debug_if_needed()
    assert len(list(tmp_path.iterdir())) == 2
