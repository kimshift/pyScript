# -*- coding: utf-8 -*-
"""adb 封装：只做「调命令 + 解析输出」，不含任何业务判断。

要点（踩过的坑）
----------------
1. **逻辑分辨率**：`wm size` 可能同时输出 `Physical size`(1440x3200) 和
   `Override size`(1080x2400)。`screencap` 与 `input tap` 用的都是 Override，
   所以取最后一个匹配值，别改成第一个。
2. **截图二进制安全**：`exec-out screencap -p` 偶发被做换行转换导致 PNG 损坏，
   解码失败时退回「先存到设备再 cat 回来」。
3. **多设备**：adb 不带 `-s` 时对多设备命令会直接失败，所以一律显式带序列号。
"""

from __future__ import annotations

import glob
import os
import re
import shutil
import subprocess
from pathlib import Path

from kit.config import expand_path

CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"

# 雷电自带 adb 的常见位置（用户装了雷电就无需手动配 adb_path）
_LDPLAYER_GLOBS = (
    "D:/leidian/*/adb.exe",
    "C:/leidian/*/adb.exe",
    "D:/LDPlayer/*/adb.exe",
    "C:/LDPlayer/*/adb.exe",
    "%LOCALAPPDATA%/leidian/*/adb.exe",
    "%LOCALAPPDATA%/LDPlayer/*/adb.exe",
)


def resolve_adb(configured: str | None = None) -> str | None:
    """按「配置 → 环境变量 → PATH → 雷电目录」顺序找 adb，找不到返回 None。"""
    if configured:
        path = expand_path(configured)
        if path and path.is_file():
            return str(path)

    env_path = os.environ.get("ADB") or os.environ.get("ANDROID_ADB")
    if env_path and Path(env_path).is_file():
        return env_path

    found = shutil.which("adb") or shutil.which("adb.exe")
    if found:
        return found

    ld_home = os.environ.get("LDPLAYER_DIR")
    if ld_home:
        candidate = Path(ld_home) / "adb.exe"
        if candidate.is_file():
            return str(candidate)

    for pattern in _LDPLAYER_GLOBS:
        for hit in sorted(glob.glob(os.path.expandvars(pattern)), reverse=True):
            if os.path.isfile(hit):
                return hit
    return None


class Adb:
    """一个 adb 会话：绑定可执行文件与目标设备。"""

    def __init__(self, exe: str | None = None, serial: str | None = None, timeout: int = 20):
        self.exe = resolve_adb(exe)
        self.serial = serial or None
        self.timeout = timeout

    # ---------- 底层 ----------

    @property
    def available(self) -> bool:
        return bool(self.exe)

    def _argv(self, args: list[str]) -> list[str]:
        argv = [self.exe or "adb"]
        if self.serial:
            argv += ["-s", self.serial]
        return argv + [str(a) for a in args]

    def run(self, args: list[str], binary: bool = False, timeout: int | None = None):
        """执行 adb 子命令；失败/超时返回 None（不抛异常，调用方按空处理）。"""
        if not self.exe:
            return None
        try:
            proc = subprocess.run(
                self._argv(args),
                capture_output=True,
                timeout=timeout or self.timeout,
                check=False,
                creationflags=CREATE_NO_WINDOW,
            )
        except (OSError, subprocess.TimeoutExpired):
            return None
        if proc.returncode != 0:
            return None
        return proc.stdout if binary else proc.stdout.decode("utf-8", "ignore")

    def version(self) -> str:
        out = self.run(["version"], timeout=10) or ""
        first = out.strip().splitlines()[0] if out.strip() else ""
        return first or "（adb 无输出）"

    # ---------- 设备 ----------

    def devices(self) -> list[tuple[str, str]]:
        """返回 [(serial, state), ...]；state 常见 device / offline / unauthorized。"""
        out = self.run(["devices"], timeout=15)
        if not out:
            return []
        pairs: list[tuple[str, str]] = []
        for line in out.splitlines()[1:]:
            line = line.strip()
            if not line or line.startswith("*"):
                continue
            parts = re.split(r"\s+", line, maxsplit=1)
            if len(parts) == 2:
                pairs.append((parts[0], parts[1]))
        return pairs

    def ensure_device(self, serial: str | None = None) -> tuple[str | None, str]:
        """确定要操作的设备：返回 (serial, 错误说明)。单设备自动选，多设备必须指定。"""
        pairs = self.devices()
        online = [s for s, state in pairs if state == "device"]
        want = serial or self.serial

        if want:
            state = next((st for s, st in pairs if s == want), None)
            if state == "device":
                self.serial = want
                return want, ""
            if state:
                return None, f"设备 {want} 状态为 {state}（unauthorized 请在手机上点「允许调试」）"
            return None, f"未找到设备 {want}；当前在线：{online or '无'}"

        if not online:
            hint = "；当前列表：" + ", ".join(f"{s}({st})" for s, st in pairs) if pairs else ""
            return None, "没有在线设备：确认 USB 调试已开启、手机保持亮屏、`adb devices` 能看到设备" + hint
        if len(online) > 1:
            return None, f"检测到多台在线设备 {online}，请用 --serial 指定一台"

        self.serial = online[0]
        return online[0], ""

    # ---------- 屏幕 ----------

    def screen_size(self) -> tuple[int, int]:
        """逻辑分辨率；解析失败返回 (0, 0)，让调用方以截图尺寸为准。"""
        out = self.run(["shell", "wm", "size"], timeout=15) or ""
        matches = re.findall(r"(\d+)x(\d+)", out)
        if not matches:
            return 0, 0
        w, h = matches[-1]  # 最后一个 = Override size，与 screencap/tap 一致
        return int(w), int(h)

    def capture_png(self) -> bytes | None:
        """截一张 PNG。主通道 exec-out，失败退回「设备侧落盘再拉回」。"""
        data = self.run(["exec-out", "screencap", "-p"], binary=True, timeout=15)
        if data and data[:8] == PNG_MAGIC:
            return data

        remote = "/sdcard/_qishui_screen.png"
        if self.run(["shell", "screencap", "-p", remote], timeout=20) is None:
            return None
        data = self.run(["exec-out", "cat", remote], binary=True, timeout=20)
        self.run(["shell", "rm", "-f", remote], timeout=10)
        if data and data[:8] == PNG_MAGIC:
            return data
        return None

    def tap(self, x: int, y: int) -> bool:
        return self.run(["shell", "input", "tap", str(int(x)), str(int(y))], timeout=10) is not None

    # ---------- 音量 ----------

    def media_volume(self) -> int | None:
        """媒体音量（stream 3）。部分设备不支持该命令，返回 None。"""
        out = self.run(["shell", "cmd", "media_session", "volume", "--stream", "3", "--get"], timeout=10) or ""
        match = re.search(r"volume is (\d+)", out)
        return int(match.group(1)) if match else None

    def toggle_mute(self) -> bool:
        """KEYCODE_VOLUME_MUTE：在原音量与 0 之间切换（本机唯一可用的静音方式）。"""
        return self.run(["shell", "input", "keyevent", "164"], timeout=10) is not None
