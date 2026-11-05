# -*- coding: utf-8 -*-
"""雷电官方命令行（ldconsole.exe）封装。

设计原则
--------
1. **只管调命令 + 复核结果**，不做业务决策（业务在 emulator.py）。
2. **返回码不可靠**：ldconsole 几乎总是返回 0，所以关键动作后必须用
   `list2` / `runninglist` / 文件是否存在来复核，不能只看 returncode。
3. **编号语义不一致**：config 里的「模拟器 id」是实例**标题**里的数字，
   而 ldconsole 用的是 0 基 `--index`。两者不做任何假设，统一走 `resolve()`
   反查；匹配规则按「标题精确 → 标题后缀 → index」依次尝试，命中哪条会写日志，
   匹配到多个或零个都直接报错并列出全部标题，避免默默操作错实例。
4. 输出编码不确定（GBK / UTF-8 都见过），统一先 utf-8 再回退 gbk。

用法
----
    from tools.ld_emulator.backends import LdConsole

    ld = LdConsole.from_emulator_path(cfg["emulator_path"])
    for inst in ld.list2():
        print(inst)
    ld.launch("12")
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from kit.log import get_logger

log = get_logger(__name__)

LD_EXE = "ldconsole.exe"

# 找不到 exe 时会尝试这些常见安装位置
_FALLBACK_DIRS = (
    r"D:\leidian\LDPlayer9",
    r"D:\Program Files\LDPlayer9",
    r"C:\LDPlayer\LDPlayer9",
    r"D:\LDPlayer\LDPlayer9",
)


class LdConsoleError(RuntimeError):
    """ldconsole 调用失败，或结果复核不通过。"""


@dataclass
class Instance:
    """list2 的一行。字段用负数下标解析，避免雷电加字段后错位。"""

    index: int
    title: str
    running: bool
    width: int
    height: int
    dpi: int
    raw: tuple[str, ...] = ()

    def __str__(self) -> str:
        state = "运行中" if self.running else "已停止"
        return f"[{self.index}] {self.title!r} {state} {self.width}x{self.height}@{self.dpi}"


class LdConsole:
    def __init__(self, exe_path: str | os.PathLike | None = None, timeout: float = 60.0):
        self.exe = self._locate(exe_path)
        self.timeout = timeout

    # ---------- 构造 ----------

    @staticmethod
    def _locate(exe_path: str | os.PathLike | None) -> Path:
        if exe_path:
            path = Path(exe_path)
            if path.is_file():
                return path
            raise LdConsoleError(f"ldconsole 不存在：{path}")
        found = shutil.which(LD_EXE)
        if found:
            return Path(found)
        for base in _FALLBACK_DIRS:
            candidate = Path(base) / LD_EXE
            if candidate.is_file():
                return candidate
        raise LdConsoleError(
            "找不到 ldconsole.exe：请确认 config.json 的 emulator_path 指向雷电安装目录，或把该目录加入 PATH"
        )

    @classmethod
    def from_emulator_path(cls, emulator_path: str, timeout: float = 60.0) -> "LdConsole":
        """用 config 的 emulator_path 推导同目录下的 ldconsole.exe。"""
        return cls(Path(emulator_path).parent / LD_EXE, timeout=timeout)

    # ---------- 底层执行 ----------

    def _run(self, *args: str | int) -> str:
        cmd = [str(self.exe), *(str(a) for a in args)]
        log.debug("ldconsole %s", " ".join(cmd[1:]))
        try:
            proc = subprocess.run(cmd, capture_output=True, timeout=self.timeout)
        except subprocess.TimeoutExpired as exc:
            raise LdConsoleError(f"命令超时（{self.timeout}s）：{' '.join(cmd[1:])}") from exc

        out = self._decode(proc.stdout)
        err = self._decode(proc.stderr).strip()
        if err:
            log.debug("stderr: %s", err)
        if proc.returncode != 0 and not out.strip():
            raise LdConsoleError(f"ldconsole 执行失败（rc={proc.returncode}）：{err or '无输出'}")
        return out

    @staticmethod
    def _decode(data: bytes) -> str:
        if not data:
            return ""
        for encoding in ("utf-8", "gbk"):
            try:
                return data.decode(encoding)
            except UnicodeDecodeError:
                continue
        return data.decode("utf-8", errors="replace")

    # ---------- 查询 ----------

    def list2(self) -> list[Instance]:
        """解析 `list2`。

        实际输出形如：
            0,雷电模拟器,0,0,0,-1,-1,1080,1920,480
        字段：index, title, 窗口句柄, 绑定句柄, 是否运行, ..., 宽, 高, dpi
        """
        instances: list[Instance] = []
        for line in self._run("list2").splitlines():
            line = line.strip()
            if not line:
                continue
            parts = [p.strip() for p in line.split(",")]
            if len(parts) < 6:
                continue
            try:
                index = int(parts[0])
            except ValueError:
                continue
            width = height = dpi = -1
            if len(parts) >= 10:
                try:
                    width, height, dpi = int(parts[-3]), int(parts[-2]), int(parts[-1])
                except ValueError:
                    pass
            instances.append(
                Instance(
                    index=index,
                    title=parts[1],
                    running=parts[4] == "1",
                    width=width,
                    height=height,
                    dpi=dpi,
                    raw=tuple(parts),
                )
            )
        return instances

    def runninglist(self) -> list[int]:
        """返回正在运行的实例 index 列表（只含纯数字行）。"""
        result: list[int] = []
        for line in self._run("runninglist").splitlines():
            line = line.strip()
            if line.isdigit():
                result.append(int(line))
        return result

    def is_running(self, target: str | int) -> bool:
        index = self.resolve(target).index
        return index in self.runninglist()

    def resolve(self, target: str | int) -> Instance:
        """把「实例 id / 标题 / index」解析成 Instance。

        规则顺序：标题精确 → 标题后缀（"雷电-12" / "雷电12" 都能被 "12" 命中）→ index。
        """
        instances = self.list2()
        if not instances:
            raise LdConsoleError("list2 返回空：没有找到任何模拟器实例")

        query = str(target).strip()

        exact = [i for i in instances if i.title == query]
        if len(exact) == 1:
            log.debug("resolve(%s) 命中标题精确匹配 -> %s", query, exact[0])
            return exact[0]

        suffix = [i for i in instances if i.title.endswith(query)]
        if len(suffix) == 1:
            log.debug("resolve(%s) 命中标题后缀匹配 -> %s", query, suffix[0])
            return suffix[0]

        if query.isdigit():
            by_index = [i for i in instances if i.index == int(query)]
            if len(by_index) == 1:
                log.debug("resolve(%s) 命中 index 匹配 -> %s", query, by_index[0])
                return by_index[0]

        titles = ", ".join(sorted(i.title for i in instances))
        if len(suffix) > 1:
            raise LdConsoleError(
                f"编号 {query} 匹配到多个实例：{[str(i) for i in suffix]}；请改用完整标题"
            )
        raise LdConsoleError(f"编号 {query} 无法定位实例。现有实例：{titles}")

    # ---------- 生命周期 ----------

    def add(self, name: str) -> None:
        """新建一个实例（等价于多开器「新建/批量新增」，但是瞬间完成）。"""
        log.info("新建实例：%s", name)
        self._run("add", "--name", name)

    def copy(self, name: str, source: str | int) -> None:
        """从已有实例复制一个（要求源实例已停止）。"""
        src = self.resolve(source)
        log.info("复制实例 %s -> %s", src.title, name)
        self._run("copy", "--name", name, "--from", src.index)

    def remove(self, target: str | int) -> None:
        self._run("remove", "--index", self.resolve(target).index)

    def launch(self, target: str | int, wait: bool = False, timeout: float = 90.0) -> Instance:
        inst = self.resolve(target)
        log.info("启动实例：%s", inst.title)
        self._run("launch", "--index", inst.index)
        if wait:
            self.wait_running(inst.index, timeout=timeout)
        return inst

    def quit(self, target: str | int) -> None:
        inst = self.resolve(target)
        log.info("关闭实例：%s", inst.title)
        self._run("quit", "--index", inst.index)

    def quit_all(self) -> None:
        log.info("关闭全部实例")
        self._run("quitall")

    def wait_running(self, target: str | int, timeout: float = 90.0, interval: float = 2.0) -> bool:
        """轮询等待实例进入运行状态；超时返回 False（不抛异常，交给调用方决定）。"""
        import time

        deadline = time.time() + timeout
        index = self.resolve(target).index
        while time.time() < deadline:
            if index in self.runninglist():
                return True
            time.sleep(interval)
        log.warning("等待实例 index=%s 启动超时（%.0fs）", index, timeout)
        return False

    def wait_stopped(self, target: str | int, timeout: float = 60.0, interval: float = 1.0) -> bool:
        import time

        deadline = time.time() + timeout
        index = self.resolve(target).index
        while time.time() < deadline:
            if index not in self.runninglist():
                return True
            time.sleep(interval)
        log.warning("等待实例 index=%s 关闭超时（%.0fs）", index, timeout)
        return False

    # ---------- 配置 ----------

    def modify(
        self,
        target: str | int,
        resolution: str | None = None,
        memory: int | None = None,
        cpu: int | None = None,
    ) -> None:
        """修改实例参数。resolution 形如 "1080,1920,480"（宽,高,dpi）。"""
        inst = self.resolve(target)
        args: list[str | int] = ["modify", "--index", inst.index]
        if resolution:
            args += ["--resolution", resolution]
        if memory:
            args += ["--memory", str(memory)]
        if cpu:
            args += ["--cpu", str(cpu)]
        if len(args) == 3:
            log.warning("modify 未指定任何参数，跳过：%s", inst.title)
            return
        log.info("修改实例参数：%s %s", inst.title, " ".join(str(a) for a in args[3:]))
        self._run(*args)

    # ---------- 应用 ----------

    def install_app(self, target: str | int, apk_path: str | os.PathLike) -> None:
        apk = Path(apk_path)
        if not apk.is_file():
            raise LdConsoleError(f"APK 不存在：{apk}")
        inst = self.resolve(target)
        if not inst.running:
            raise LdConsoleError(f"实例 {inst.title} 未运行，无法安装 APK")
        log.info("安装 %s -> %s", apk.name, inst.title)
        self._run("installapp", "--index", inst.index, "--filename", str(apk))

    def uninstall_app(self, target: str | int, package: str) -> None:
        inst = self.resolve(target)
        self._run("uninstallapp", "--index", inst.index, "--packagename", package)

    def run_app(self, target: str | int, package: str) -> None:
        inst = self.resolve(target)
        self._run("runapp", "--index", inst.index, "--packagename", package)

    def adb(self, target: str | int, command: str) -> str:
        """在实例内执行 adb 命令，例如 'shell pm list packages'。"""
        inst = self.resolve(target)
        return self._run("adb", "--index", inst.index, "--command", command)

    # ---------- 备份 / 还原 ----------

    def backup(self, target: str | int, file_path: str | os.PathLike, verify: bool = True) -> Path:
        dest = Path(file_path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        inst = self.resolve(target)
        log.info("备份 %s -> %s", inst.title, dest)
        # 旧文件会让「是否生成成功」的判断失真
        if verify and dest.exists():
            dest.unlink()
        self._run("backup", "--index", inst.index, "--file", str(dest))
        if verify and not dest.exists():
            raise LdConsoleError(f"备份命令已执行但文件未生成：{dest}")
        return dest

    def restore(self, target: str | int, file_path: str | os.PathLike) -> None:
        src = Path(file_path)
        if not src.is_file():
            raise LdConsoleError(f"备份文件不存在：{src}")
        inst = self.resolve(target)
        log.info("还原 %s <- %s", inst.title, src)
        self._run("restore", "--index", inst.index, "--file", str(src))

    # ---------- 窗口 ----------

    def sort_wnd(self) -> None:
        log.info("排列全部窗口")
        self._run("sortWnd")
