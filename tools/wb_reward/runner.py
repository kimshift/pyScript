# -*- coding: utf-8 -*-
"""WorkBuddy 积分任务调度包装器。

来源：迁移自 D:\\workplace\\WorkBuddy\\wb_reward_runner.py（2026-11-05）。

职责：由 Windows 计划任务拉起，调用 workbuddy-reward-helper 的 main.py 子命令，
把执行过程写入 logs/wb_reward/scheduler.log，结果摘要写入同目录的 result.log。

日志语言
--------
`scheduler.log` 全部为**中文叙述**，便于直接阅读。skill 返回的 JSON 会被翻译成
一句话结论（如「签到成功：+100 积分，连续签到 28 天」）；只有在**执行失败**或
**出现未知状态**时，才额外附一行原始 JSON 供排查。

`result.log` 由 skill 自己写入（英文状态码），本脚本只负责重定向它的位置，
不在其中插入内容，避免两个写入方互相覆盖。

迁移后的改动（相对原脚本）
--------------------------
1. **不再写死 WorkBuddy 内置 Python**（`...\\binaries\\python\\versions\\3.13.12\\python.exe`）。
   客户端一旦升级，那个版本号目录就变了，任务会静默失败。现在默认用当前解释器
   （即项目 .venv），可用 config/wb_reward.json 的 `python` 字段覆盖。
2. 路径 / 超时 / 重试 / 日志上限全部外置到 config/wb_reward.json。
3. **新增跨任务互斥锁**：checkin 与 travel 的触发时间可能挨得很近，而计划任务的
   MultipleInstances 只在同一任务内生效，不同任务会并发跑同一套凭据逻辑。
4. WorkBuddy 客户端存活探测改用 psutil，省掉每次 fork 一个 `tasklist` 进程。
5. 退出码语义统一，日志里直接写出中文含义，并记录单次耗时。

日志格式保持原样：**按执行块整体置顶**（最新一次在最前，块内保序），
带 1MB 轮转与 2000 行上限。
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from kit.config import expand_path, load_config as load_json_config
from kit.paths import config_path, log_dir

# ---------- 退出码语义 ----------
EXIT_OK = 0            # 成功
EXIT_BIZ = 1           # 业务失败（skill 返回非零 / 未授权等）
EXIT_ENV = 2           # 环境缺失（skill 目录、解释器不存在）
EXIT_TIMEOUT = 3       # 超时
EXIT_IO = 4            # IO / 子进程启动失败
EXIT_LOCKED = 5        # 已有实例在跑，本次跳过

EXIT_TEXT = {
    EXIT_OK: "成功",
    EXIT_BIZ: "业务失败",
    EXIT_ENV: "环境缺失",
    EXIT_TIMEOUT: "超时",
    EXIT_IO: "IO 错误",
    EXIT_LOCKED: "已跳过（有实例在运行）",
}

ACTION_TEXT = {
    "all": "签到 + 旅行",
    "checkin": "签到",
    "travel": "旅行",
    "status": "状态查询",
    "health": "登录态检查",
}

# 日志统一放仓库根目录 logs/<工具名>/，配置统一放仓库根 config/<工具名>.json
LOG_DIR = log_dir("wb_reward")
LOG_FILE = LOG_DIR / "scheduler.log"
LOCK_FILE = LOG_DIR / "runner.lock"
CONFIG_FILE = config_path("wb_reward")

DEFAULTS = {
    "skill_scripts": "",
    "python": "",
    "run_timeout": 180,
    "retry_max": 3,
    "retry_delay": 6,
    "lock_timeout": 300,
    "log_max_bytes": 1024 * 1024,
    "log_max_lines": 2000,
    "token_info": "",
}

# 候选 skill 目录（config 未指定时按顺序探测）
SKILL_CANDIDATES = (
    Path.home() / ".workbuddy" / "skills" / "workbuddy-reward-helper" / "scripts",
)

CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

_BLOCK: list[str] = []
_CFG: dict = {}


# ---------- 配置 ----------

def load_config() -> dict:
    """config/wb_reward.json 打底 + config/wb_reward.local.json 覆盖（机器私有，不入库）。"""
    cfg = dict(DEFAULTS)
    try:
        cfg.update(load_json_config(CONFIG_FILE))
    except (OSError, ValueError) as exc:
        _log(f"配置文件读取失败（改用默认值）：{exc}")
    return cfg


def skill_scripts_dir() -> Path | None:
    """定位 workbuddy-reward-helper 的 scripts 目录。"""
    configured = _CFG.get("skill_scripts") or ""
    if configured:
        path = expand_path(configured)
        return path if path and path.is_dir() else None
    for candidate in SKILL_CANDIDATES:
        if candidate.is_dir():
            return candidate
    return None


def python_exe() -> str:
    """子进程解释器：默认用当前解释器（项目 .venv），可由 config 覆盖。"""
    configured = _CFG.get("python") or ""
    if configured and Path(configured).is_file():
        return configured
    return sys.executable


# ---------- 日志（按执行块整体置顶） ----------

def _log(line: str) -> None:
    """记录一行（先进内存块，块满 50 行或结束时整体 flush）。"""
    _BLOCK.append(line)
    if len(_BLOCK) >= 50:
        _flush_block()


def _flush_block() -> None:
    """把当前执行块整体写到日志文件最前，块内保序。"""
    global _BLOCK
    if not _BLOCK:
        return
    block, _BLOCK = _BLOCK, []
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        _rotate_if_needed()
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        head = f"----- {ts} -----\n"
        body = "".join(f"[{ts}] {part}\n" for ln in block for part in str(ln).split("\n"))

        existing: list[str] = []
        if LOG_FILE.is_file():
            try:
                existing = LOG_FILE.read_text(encoding="utf-8-sig").splitlines(keepends=True)
            except OSError:
                existing = []

        merged = [head, body, "\n"] + existing
        merged = merged[: int(_CFG.get("log_max_lines", 2000))]

        tmp = LOG_FILE.with_suffix(".log.tmp")
        # utf-8-sig：Windows 记事本/PowerShell 打开中文不乱码
        tmp.write_text("".join(merged), encoding="utf-8-sig")
        os.replace(tmp, LOG_FILE)
    except OSError:
        pass  # 日志失败不影响任务本身


def _rotate_if_needed() -> None:
    limit = int(_CFG.get("log_max_bytes", 1024 * 1024))
    try:
        if LOG_FILE.is_file() and LOG_FILE.stat().st_size >= limit:
            archive = LOG_FILE.with_suffix(".log.1")
            if archive.exists():
                archive.unlink()
            os.replace(LOG_FILE, archive)
    except OSError:
        pass


# ---------- 互斥锁 ----------

class RunLock:
    """跨任务的运行锁：同一时刻只允许一个 runner 实例。

    用「独占创建 + PID 校验」实现：进程崩溃留下的陈旧锁会被自动回收，
    不会把后续所有任务永久挡在门外。
    """

    def __init__(self, path: Path, timeout: int):
        self.path = path
        self.timeout = timeout
        self._fd: int | None = None

    def __enter__(self) -> "RunLock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        deadline = time.time() + self.timeout
        while True:
            try:
                fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_RDWR)
                os.write(fd, str(os.getpid()).encode())
                self._fd = fd
                return self
            except FileExistsError:
                if self._is_stale():
                    self._clear_stale()
                    continue
                if time.time() > deadline:
                    raise TimeoutError("另一个任务实例正在运行")
                time.sleep(2)

    def __exit__(self, *exc_info) -> None:
        if self._fd is not None:
            os.close(self._fd)
            self._fd = None
        try:
            self.path.unlink()
        except OSError:
            pass

    def _is_stale(self) -> bool:
        try:
            pid = int(self.path.read_text(encoding="utf-8").strip() or 0)
            age = time.time() - self.path.stat().st_mtime
        except (OSError, ValueError):
            return True
        if age > self.timeout:
            return True
        try:
            import psutil

            return pid > 0 and not psutil.pid_exists(pid)
        except Exception:
            return False

    def _clear_stale(self) -> None:
        try:
            self.path.unlink()
        except OSError:
            pass


# ---------- 子进程调用 ----------

def _run_main(args: list[str]) -> tuple[int, str, str]:
    """调用 skill 的 main.py，返回 (returncode, stdout, stderr)。

    通过 WB_REWARD_LOG_DIR 把 skill 自带的 result.log 重定向到本工具日志目录；
    传输层瞬时故障（SSL EOF / 超时 / 连接重置）自动重试，业务失败不重试。
    """
    scripts = skill_scripts_dir()
    main_py = (scripts or Path()) / "main.py"
    env = dict(os.environ)
    env["WB_REWARD_LOG_DIR"] = str(LOG_DIR)

    last: tuple[int, str, str] = (EXIT_BIZ, "", "")
    retry_max = int(_CFG.get("retry_max", 3))
    retry_delay = float(_CFG.get("retry_delay", 6))

    for attempt in range(1, retry_max + 1):
        try:
            proc = subprocess.run(
                [python_exe(), str(main_py)] + args,
                capture_output=True,
                text=True,
                timeout=float(_CFG.get("run_timeout", 180)),
                cwd=str(scripts),
                env=env,
                creationflags=CREATE_NO_WINDOW,
            )
        except subprocess.TimeoutExpired:
            return (EXIT_TIMEOUT, "", "TIMEOUT")
        except OSError as exc:
            return (EXIT_IO, "", str(exc))

        out = (proc.stdout or "").strip()
        err = (proc.stderr or "").strip()
        last = (proc.returncode, out, err)

        if attempt < retry_max and _is_transient(out, err):
            _log(f"网络抖动，第 {attempt}/{retry_max} 次重试（{retry_delay:.0f} 秒后）")
            time.sleep(retry_delay)
            continue
        break

    return last


def _is_transient(out: str, err: str) -> bool:
    """判断是否为可重试的传输层瞬时故障（401 等业务错误不重试）。"""
    blob = f"{out} {err}"
    if "401" in blob or "unauthorized" in blob.lower():
        return False
    markers = (
        "UNEXPECTED_EOF_WHILE_READING",
        "SSLError",
        "CERTIFICATE_VERIFY_FAILED",
        "ConnectionResetError",
        "Connection aborted",
        "ConnectionRefusedError",
        "timed out",
        "TimeoutError",
        "RemoteDisconnected",
        "IncompleteRead",
        "网络异常",
        "Temporary failure in name resolution",
    )
    return any(marker in blob for marker in markers)


# ---------- 把 skill 返回的 JSON 翻译成中文 ----------

def _fmt_time(ts) -> str:
    try:
        return time.strftime("%Y-%m-%d %H:%M", time.localtime(float(ts)))
    except (TypeError, ValueError, OSError):
        return "未知时间"


def _describe_checkin(data: dict) -> str | None:
    status = data.get("status")
    if status == "success":
        return f"签到成功：+{data.get('credit', '?')} 积分，连续签到 {data.get('streak_days', '?')} 天"
    if status == "already_checked":
        return "今日已签到，无需重复"
    if status == "failed":
        return f"签到失败：{data.get('message') or data.get('reason') or '未说明原因'}"
    return None


def _describe_travel(data: dict) -> str | None:
    status = data.get("status")
    if status == "claimed":
        return f"旅行奖励已领取：+{data.get('reward_credit', '?')} 积分"
    if status == "departed":
        return f"已出发，预计 {_fmt_time(data.get('arrive_at'))} 到达"
    if status == "daily_limit_reached":
        return "今日旅行次数已达上限"
    if status == "failed":
        return f"旅行失败：{data.get('message') or data.get('reason') or '未说明原因'}"
    return None


def _describe_status(data: dict) -> str | None:
    checkin = data.get("checkin_status") or {}
    travel = data.get("travel_status") or {}
    parts: list[str] = []
    if checkin:
        checked = checkin.get("today_checked_in")
        if checked is True:
            parts.append("今日已签到")
        elif checked is False:
            # 上游接口已知缺陷：v5.3.8 实测签到成功后该字段仍可能为 false，
            # 所以这里不能当结论报「今日未签到」，只说明接口返回了什么。
            parts.append("签到接口未记录（该字段已知不准，以「签到」任务结果为准）")
        else:
            parts.append("签到状态未知")
        if checkin.get("streak_days") is not None:
            parts.append(f"连续 {checkin['streak_days']} 天")
    if travel:
        parts.append("今日旅行已达上限" if travel.get("daily_limit_reached") else "旅行空闲")
        if travel.get("arrive_at"):
            parts.append(f"到达时间 {_fmt_time(travel['arrive_at'])}")
    return "；".join(parts) or None


def _describe_growth(data: dict) -> str | None:
    if not any(key in data for key in ("tiers", "streak_days", "claimable")):
        return None
    tiers = data.get("tiers") or {}
    tier_text = "，".join(
        f"{name} {((info or {}).get('status') or '未知')}" for name, info in tiers.items()
    ) or "无"
    cards = (data.get("makeup_cards") or {}).get("balance", "?")
    return (
        f"成长计划：连续 {data.get('streak_days', '?')} 天，"
        f"下一档 {data.get('next_tier', '?')}（还差 {data.get('next_tier_remaining', '?')}），"
        f"补签卡 {cards} 张，各档状态：{tier_text}"
    )


def _describe_result(args: list[str], out: str) -> str | None:
    """把 JSON 输出翻译成一句中文；识别不了就返回 None（调用方再决定要不要写原文）。"""
    if not out:
        return None
    try:
        data = json.loads(out)
    except (ValueError, TypeError):
        return None
    if not isinstance(data, dict):
        return None

    if "checkin_status" in data or "travel_status" in data:
        return _describe_status(data)
    task = data.get("task") or (args[0] if args else "")
    if task == "checkin":
        return _describe_checkin(data)
    if task == "travel":
        return _describe_travel(data)
    if task == "growth" or "tiers" in data:
        return _describe_growth(data)
    return None


# ---------- 业务动作 ----------

def _client_text() -> str:
    """执行瞬间 WorkBuddy 客户端是否在运行（仅用于日志自证）。"""
    try:
        import psutil

        for proc in psutil.process_iter(["name"]):
            if (proc.info.get("name") or "").lower().startswith("workbuddy"):
                return "运行中"
        return "未运行"
    except Exception:
        return "未知"


def _health() -> int:
    """登录态检查：token 剩余有效期 + 一次只读探活。"""
    _log("登录态检查：读取本地登录信息")
    info_path = _CFG.get("token_info") or str(
        Path(os.environ.get("LOCALAPPDATA", ""))
        / "CodeBuddyExtension" / "Data" / "Public" / "auth" / "workbuddy-desktop.info"
    )
    expires_at = None
    try:
        with open(info_path, "r", encoding="utf-8") as fh:
            expires_at = ((json.load(fh).get("auth") or {}).get("expiresAt"))
    except (OSError, ValueError, TypeError) as exc:
        _log(f"登录信息读取失败：{exc}")

    if isinstance(expires_at, int) and expires_at > 0:
        ts = expires_at / 1000.0 if expires_at > 1e11 else float(expires_at)
        days_left = (ts - time.time()) / 86400.0
        _log(f"登录有效期至 {_fmt_time(ts)}，剩余 {days_left:.1f} 天")
        if days_left < 7:
            _log(f"注意：登录状态将在 {days_left:.1f} 天后过期，请打开 WorkBuddy 客户端刷新登录")
    else:
        _log("登录有效期：读取不到")

    _log("发起只读探活")
    code, out, err = _run_main(["status"])
    summary = _describe_result(["status"], out)
    if summary:
        _log(f"探活结果：{summary}")
    elif out:
        _log(f"探活原始返回：{out[:800]}")
    if err:
        _log(f"探活错误输出：{err[:400]}")
    return code


def _growth_auto() -> int:
    """成长计划：先查状态，只有明确存在可领取档位时才领（幂等，绝不重复领）。"""
    _log("成长计划：查询当前状态")
    code, out, err = _run_main(["growth", "status"])
    if code != 0:
        _log(f"成长计划：状态查询失败（退出码 {code}）")
        if out:
            _log(f"原始返回：{out[:800]}")
        if err:
            _log(f"错误输出：{err[:600]}")
        return code

    try:
        data = json.loads(out)
    except (ValueError, TypeError):
        _log("成长计划：状态解析失败，原始返回如下")
        _log(f"原始返回：{out[:800]}")
        return EXIT_BIZ

    summary = _describe_growth(data)
    if summary:
        _log(summary)

    claimable = data.get("claimable") or []
    if not claimable:
        _log("成长计划：暂无可领取档位，跳过领取")
        return EXIT_OK

    _log(f"成长计划：发现 {len(claimable)} 个可领取档位 {claimable}，开始领取")
    ccode, cout, cerr = _run_main(["growth", "claim-all"])
    if ccode == EXIT_OK:
        _log("成长计划：领取完成")
        if cout:
            _log(f"领取返回：{cout[:800]}")
    else:
        _log(f"成长计划：领取失败（退出码 {ccode}）")
        if cout:
            _log(f"领取原始返回：{cout[:800]}")
        if cerr:
            _log(f"领取错误输出：{cerr[:600]}")
    return ccode


# ---------- 入口 ----------

def run(argv: list[str]) -> int:
    global _CFG
    _CFG = load_config()

    args = argv or ["all"]
    action = args[0]
    if action == "growth":
        action_text = f"成长计划（{args[1] if len(args) > 1 else 'status'}）"
    else:
        action_text = ACTION_TEXT.get(action, action)

    scripts = skill_scripts_dir()
    if scripts is None:
        _log("启动失败：找不到 workbuddy-reward-helper/scripts，请检查 config/wb_reward.json 的 skill_scripts")
        _flush_block()
        return EXIT_ENV
    if not (scripts / "main.py").is_file():
        _log(f"启动失败：skill 入口不存在 {scripts / 'main.py'}")
        _flush_block()
        return EXIT_ENV
    if not Path(python_exe()).is_file():
        _log(f"启动失败：解释器不存在 {python_exe()}")
        _flush_block()
        return EXIT_ENV

    try:
        lock = RunLock(LOCK_FILE, int(_CFG.get("lock_timeout", 300)))
        lock.__enter__()
    except TimeoutError:
        _log("跳过本次执行：另一个任务实例正在运行")
        _flush_block()
        return EXIT_LOCKED

    started = time.time()
    code = EXIT_BIZ
    try:
        _log(f"开始执行：{action_text}（WorkBuddy 客户端：{_client_text()}）")
        if args == ["growth", "auto"]:
            code = _growth_auto()
        elif args == ["health"]:
            code = _health()
        else:
            code, out, err = _run_main(args)
            summary = _describe_result(args, out)
            if summary:
                _log(f"执行结果：{summary}")
            if code != EXIT_OK or summary is None:
                if out:
                    _log(f"原始返回：{out[:800]}")
            if err:
                _log(f"错误输出：{err[:600]}")
        return code
    except subprocess.TimeoutExpired:
        _log(f"执行超时：超过 {_CFG.get('run_timeout')} 秒")
        return EXIT_TIMEOUT
    except OSError as exc:
        _log(f"执行出错：{exc}")
        return EXIT_IO
    finally:
        elapsed = time.time() - started
        _log(f"执行结束：{EXIT_TEXT.get(code, f'未知（{code}）')}，耗时 {elapsed:.1f} 秒")
        _flush_block()
        lock.__exit__(None, None, None)


def main(argv: list[str] | None = None) -> int:
    try:
        return run(list(sys.argv[1:] if argv is None else argv))
    except BaseException as exc:  # pythonw 无控制台，未捕获异常必须落盘
        try:
            _log(f"未捕获异常：{type(exc).__name__}: {exc}")
            _flush_block()
        except Exception:
            pass
        return EXIT_BIZ
