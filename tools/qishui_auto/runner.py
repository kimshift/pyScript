# -*- coding: utf-8 -*-
"""主循环与命令入口。

一轮 = 截图 → OCR → 决策 → 点击。单轮约 1.2~1.8s（截图 0.5~0.9s + OCR 0.7s），
参考实现实测一轮约 1.5s，这里保持同样的节奏，只把参数外置到配置。

改进点（相对参考的单文件脚本）
-----------------------------
- 全部可调参数进 `config/qishui.json`，改文案不用动代码；
- `--dry-run` 只识别不点击，先确认「它会点哪儿」再真跑；
- `check` 自检把 adb / 设备 / 分辨率 / OCR / 当前屏幕识别结果一次看清；
- 运行日志落 `logs/qishui_auto/run.log`，命中截图落 `logs/qishui_auto/debug_clicks/`；
- 结束打印统计（每个目标点了几次、总耗时），Ctrl+C 也会恢复音量。
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from collections import Counter

from kit.config import local_config_path
from kit.log import get_logger
from tools.qishui_auto import ACTION_TEXT, ACTIONS
from tools.qishui_auto.adb import Adb
from tools.qishui_auto.config import CONFIG_FILE, Settings
from tools.qishui_auto.config import load as load_settings
from tools.qishui_auto.match import Decision, decide
from tools.qishui_auto.ocr import OcrEngine, decode_png, save_debug
from tools.qishui_auto.uia import UiaChannel

EXIT_OK = 0
EXIT_CONFIG = 1  # 参数 / 配置错误
EXIT_RUNTIME = 2  # 运行失败（没有 adb、设备离线、OCR 不可用）

log = get_logger("qishui_auto")


# ------------------------- CLI -------------------------


class _Parser(argparse.ArgumentParser):
    """参数错误统一返回退出码 1（argparse 默认是 2）。"""

    def error(self, message):
        self.print_usage(sys.stderr)
        print(f"参数错误：{message}", file=sys.stderr)
        raise SystemExit(EXIT_CONFIG)


def build_parser() -> argparse.ArgumentParser:
    parser = _Parser(
        prog="python -m tools.qishui_auto",
        description="汽水音乐自动看广告（纯 UI 自动化：只点界面上真实存在的按钮）",
        epilog="动作：" + "；".join(f"{name}={ACTION_TEXT[name]}" for name in ACTIONS),
    )
    parser.add_argument("action", nargs="?", default="run", choices=ACTIONS, help="默认 run")
    parser.add_argument("--serial", help="指定设备序列号（多设备时必填）")
    parser.add_argument("--adb", dest="adb_path", help="adb 可执行文件路径（默认自动探测）")
    parser.add_argument("--dry-run", action="store_true", help="只识别不点击")
    parser.add_argument("--max-clicks", type=int, help="点够多少次自动停（0=不限）")
    parser.add_argument("--mute", action="store_true", help="本次运行静音（退出恢复）")
    parser.add_argument("--no-uia", action="store_true", help="关闭 uiautomator 兜底通道")
    return parser


def apply_overrides(settings: Settings, args: argparse.Namespace) -> Settings:
    """命令行优先于配置文件。"""
    if args.serial:
        settings.serial = args.serial
    if args.adb_path:
        settings.adb_path = args.adb_path
    if args.dry_run:
        settings.dry_run = True
    if args.max_clicks is not None:
        settings.max_clicks = max(0, args.max_clicks)
    if args.mute:
        settings.mute_on_start = True
    if args.no_uia:
        settings.uia_mode = "off"
    return settings


def attach_file_log(path) -> None:
    """把同一份日志再写一份到 logs/qishui_auto/run.log（重复调用不重复加）。"""
    for handler in log.handlers:
        if isinstance(handler, logging.FileHandler):
            return
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        handler = logging.FileHandler(path, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s | %(message)s", datefmt="%m-%d %H:%M:%S"))
        log.addHandler(handler)
    except OSError as exc:
        log.warning("日志文件不可写（只输出到控制台）：%s", exc)


# ------------------------- 运行 -------------------------


class Runner:
    def __init__(self, settings: Settings):
        self.s = settings
        self.adb = Adb(settings.adb_path, settings.serial)
        self.ocr = OcrEngine(settings.ocr_min_score, settings.ocr_max_width, settings.ocr_use_cls)
        self.uia = UiaChannel(self.adb, settings.uia_mode, settings.uia_timeout, settings.uia_max_fail, log.info)
        self.size = (0, 0)
        self.stats: Counter[str] = Counter()
        self.seq = 0
        self.frames = 0
        self.idle = 0
        self.capture_fail = 0
        self.muted = False
        self.saved_volume: int | None = None
        self.last_click = {"target": "", "x": -1, "y": -1, "ts": 0.0}
        self._started = 0.0

    # ---------- 对外 ----------

    def run(self) -> int:
        serial, err = self.adb.ensure_device()
        if not serial:
            log.error("%s", err)
            return EXIT_RUNTIME

        self.size = self.adb.screen_size()
        self._banner(serial)
        if not self._channels_ready():
            return EXIT_RUNTIME

        self._mute_on_start()
        self._started = time.time()
        try:
            while not self._limit_reached():
                if self._step():
                    self.idle = 0
                    time.sleep(self.s.click_cooldown)
                else:
                    self.idle += 1
                    if self.idle % self.s.idle_report_every == 0:
                        log.info("· 等待中…（%d 轮未发现可点按钮）", self.idle)
                    time.sleep(self.s.poll_interval)
        except KeyboardInterrupt:
            log.info("已手动停止（Ctrl+C）")
        finally:
            self._unmute()
            self._summary()
        return EXIT_OK

    # ---------- 启动 ----------

    def _banner(self, serial: str) -> None:
        width, height = self.size
        log.info("汽水音乐自动看广告：设备 %s，逻辑分辨率 %s", serial, f"{width}x{height}" if width else "以截图为准")
        log.info(
            "领奖 %s ｜ 关闭 %s ｜ 跳过 %s",
            self.s.reward_targets,
            self.s.close_targets,
            self.s.skip_targets if self.s.enable_skip else "已禁用",
        )
        log.info("通道：OCR%s ｜ uiautomator=%s ｜ 停止按 Ctrl+C", "" if self.s.use_ocr else "（关闭）", self.s.uia_mode)
        if self.s.dry_run:
            log.info("dry-run：只识别不点击")

    def _channels_ready(self) -> bool:
        ok, why = OcrEngine.deps_status()
        if self.s.use_ocr and not ok:
            log.error("OCR 不可用：%s", why)
            return False

        if self.s.uia_enabled:
            began = time.time()
            usable = self.uia.probe()
            log.info(
                "uiautomator 探测：%s（%.1fs）",
                "可用，仅作兜底" if usable else "不可用（等不到 idle），只走 OCR",
                time.time() - began,
            )
        if not self.s.use_ocr and not self.uia.usable:
            log.error("没有可用通道：请先 `mise run qs:setup` 安装 OCR 依赖")
            return False
        return True

    # ---------- 单轮 ----------

    def _step(self) -> bool:
        decision: Decision | None = None
        screen = None
        source = "ocr"

        if self.s.use_ocr:
            png = self.adb.capture_png()
            if png is None:
                self.capture_fail += 1
                if self.capture_fail % 10 == 1:
                    log.warning("截图失败（累计 %d 次）：检查 adb 连接与手机是否锁屏", self.capture_fail)
            else:
                screen = decode_png(png)
                if screen is not None:
                    height, width = screen.shape[:2]
                    self.size = (width, height)  # 以真实截图为准，避免 wm size 与实际不一致
                    self.frames += 1
                    decision = decide(
                        self.ocr.nodes(screen),
                        width,
                        height,
                        self.s.rules,
                        self.s.cancel_word,
                        self.s.live_keyword,
                        self.s.fuzzy,
                    )

        if decision is None and self.uia.usable:
            nodes = self.uia.nodes()
            if nodes:
                width, height = self.size
                decision = decide(nodes, width, height, self.s.rules, self.s.cancel_word, self.s.live_keyword, self.s.fuzzy)
                if decision is not None:
                    source = "uia"

        return self._act(decision, screen, source)

    def _act(self, decision: Decision | None, screen, source: str) -> bool:
        if decision is None:
            return False
        if self._duplicate(decision):
            return False

        self.seq += 1
        self.stats[decision.action] += 1
        self.last_click.update(target=decision.target, x=decision.x, y=decision.y, ts=time.time())

        extra = f"（{decision.reason}）" if decision.reason else ""
        if self.s.dry_run:
            log.info("[dry-run] 会点 #%d %s「%s」@(%d,%d)%s", self.seq, decision.target, decision.label, decision.x, decision.y, extra)
        else:
            log.info(">>> 点击 #%d %s「%s」@(%d,%d) via %s%s", self.seq, decision.target, decision.label, decision.x, decision.y, source, extra)
            if not self.adb.tap(decision.x, decision.y):
                log.warning("点击命令执行失败（%s @%d,%d）", decision.target, decision.x, decision.y)

        if self.s.save_click_images and not self.s.dry_run:
            save_debug(screen, decision.label, decision.x, decision.y, self.s.debug_dir, self.seq, decision.action)
        return True

    def _duplicate(self, decision: Decision) -> bool:
        """同一目标、同一位置、冷却时间内的重复命中一律忽略（防止连点）。"""
        last = self.last_click
        if decision.target != last["target"]:
            return False
        near = abs(decision.x - last["x"]) < 20 and abs(decision.y - last["y"]) < 20
        return near and (time.time() - last["ts"]) < self.s.dedupe_seconds

    def _limit_reached(self) -> bool:
        return bool(self.s.max_clicks) and sum(self.stats.values()) >= self.s.max_clicks

    # ---------- 音量 ----------

    def _mute_on_start(self) -> None:
        if not self.s.mute_on_start or self.s.dry_run:
            return
        volume = self.adb.media_volume()
        if volume is None:
            log.warning("读不到媒体音量，跳过自动静音（不影响点击）")
            return
        if volume == 0:
            log.info("当前已是静音，跳过")
            return
        self.saved_volume = volume
        self.adb.toggle_mute()
        time.sleep(0.3)
        if self.adb.media_volume() == 0:
            self.muted = True
            log.info("已静音（原音量 %d，退出时恢复）", volume)
        else:
            log.warning("静音未生效，继续运行")

    def _unmute(self) -> None:
        if not self.muted:
            return
        if self.adb.media_volume() == 0:  # 只在自己静过音时恢复，别改用户手动调的音量
            self.adb.toggle_mute()
        self.muted = False
        log.info("已恢复音量")

    # ---------- 收尾 ----------

    def _summary(self) -> None:
        elapsed = time.time() - self._started if self._started else 0.0
        total = sum(self.stats.values())
        detail = "｜".join(f"{name} {count} 次" for name, count in self.stats.items()) or "无点击"
        log.info(
            "本次结束：%d 次点击（%s），识别 %d 帧，耗时 %.0fs%s",
            total,
            detail,
            self.frames,
            elapsed,
            "，dry-run 未真正点击" if self.s.dry_run else "",
        )


# ------------------------- 自检 / 设备 -------------------------


def action_devices(settings: Settings) -> int:
    adb = Adb(settings.adb_path, settings.serial)
    if not adb.available:
        print("未找到 adb：请安装 platform-tools，或在 config/qishui.local.json 里填 adb_path")
        return EXIT_RUNTIME
    print(f"adb：{adb.exe}")
    pairs = adb.devices()
    if not pairs:
        print("没有设备。请开启 USB 调试并确认 `adb devices` 能看到设备。")
        return EXIT_RUNTIME
    for serial, state in pairs:
        print(f"  {serial}\t{state}")
    return EXIT_OK


def action_check(settings: Settings) -> int:
    """只读自检：不点击、不改音量，把关键环节一个个说清楚。"""
    problems: list[str] = []

    print(f"配置文件：{CONFIG_FILE}（local 覆盖 {'有' if local_config_path(CONFIG_FILE).is_file() else '无'}）")

    adb = Adb(settings.adb_path, settings.serial)
    if not adb.available:
        problems.append("未找到 adb（安装 platform-tools，或配置 adb_path）")
        print("[x] adb：未找到")
        _print_problems(problems)
        return EXIT_RUNTIME
    print(f"[✓] adb：{adb.exe}（{adb.version()}）")

    serial, err = adb.ensure_device()
    if not serial:
        problems.append(err)
        print(f"[x] 设备：{err}")
        _print_problems(problems)
        return EXIT_RUNTIME
    print(f"[✓] 设备：{serial}")

    size = adb.screen_size()
    print(f"[✓] 分辨率（wm size）：{size[0]}x{size[1]}" if size[0] else "[!] 分辨率：wm size 解析失败，下面以截图尺寸为准")

    ok, why = OcrEngine.deps_status()
    if not ok:
        problems.append(f"OCR 不可用：{why}")
        print(f"[x] OCR：{why}")
        _print_problems(problems)
        return EXIT_RUNTIME

    engine = OcrEngine(settings.ocr_min_score, settings.ocr_max_width, settings.ocr_use_cls)
    elapsed = engine.warmup()
    print(f"[✓] OCR：{why}，加载+试跑 {elapsed:.1f}s")

    uia = UiaChannel(adb, settings.uia_mode, settings.uia_timeout, settings.uia_max_fail)
    if settings.uia_enabled:
        began = time.time()
        usable = uia.probe()
        print(f"[{'✓' if usable else '-'}] uiautomator：{'可用（仅兜底）' if usable else '不可用'}（{time.time() - began:.1f}s）")

    png = adb.capture_png()
    if png is None:
        problems.append("截图失败：确认手机亮屏未锁屏、adb 有权限")
        print("[x] 截图：失败")
        _print_problems(problems)
        return EXIT_RUNTIME
    screen = decode_png(png)
    if screen is None:
        problems.append("截图解码失败（PNG 损坏）：可重试，或检查 adb 版本")
        print("[x] 截图：PNG 解码失败")
        _print_problems(problems)
        return EXIT_RUNTIME

    height, width = screen.shape[:2]
    print(f"[✓] 截图：{width}x{height}")
    nodes = engine.nodes(screen)
    print(f"[✓] 识别到 {len(nodes)} 段文字，前 12 条：")
    for node in nodes[:12]:
        print(f"      「{node.label}」@({node.cx},{node.cy}) 置信度 {node.score:.2f}")

    decision = decide(nodes, width, height, settings.rules, settings.cancel_word, settings.live_keyword, settings.fuzzy)
    if decision:
        print(f"[→] 当前屏幕会点：{decision.target}「{decision.label}」@({decision.x},{decision.y}){decision.reason}")
    else:
        print("[→] 当前屏幕没有可点目标（未进入看广告页面时这是正常的）")

    _print_problems(problems)
    return EXIT_OK if not problems else EXIT_RUNTIME


def _print_problems(problems: list[str]) -> None:
    if problems:
        print("\n需要处理：")
        for item in problems:
            print(f"  - {item}")
    else:
        print("\n自检通过，可以 mise run qs:run 开跑（先加 --dry-run 更稳）。")


# ------------------------- 入口 -------------------------


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(sys.argv[1:] if argv is None else list(argv))
    try:
        settings = apply_overrides(load_settings(), args)
    except (OSError, ValueError) as exc:
        print(f"配置读取失败：{exc}", file=sys.stderr)
        return EXIT_CONFIG

    attach_file_log(settings.log_file)

    if args.action == "devices":
        return action_devices(settings)
    if args.action == "check":
        return action_check(settings)
    return Runner(settings).run()


if __name__ == "__main__":
    raise SystemExit(main())
