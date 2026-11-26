# -*- coding: utf-8 -*-
"""无线调试相关的单元测试：地址判定、连接结果解析、配置读写的容错。

真机配对需要手机配合，这里只覆盖不依赖设备的逻辑——恰恰是最容易写错的
地方：adb 的 connect 失败时通常仍返回 rc=0，只能看输出文本判断。
"""

import pytest

from tools.qishui_auto import runner
from tools.qishui_auto.adb import Adb, _is_network_serial
from tools.qishui_auto.runner import EXIT_OK, EXIT_RUNTIME


class FakeAdb(Adb):
    """把 run() 换成固定输出，不真的调 adb。"""

    def __init__(self, output="", pairs=None):
        self._output = output
        self._pairs = pairs or []
        self.exe = "fake-adb"
        self.serial = None
        self.timeout = 5
        self.calls = []

    def run(self, args, binary=False, timeout=None):
        self.calls.append(list(args))
        return self._output

    def devices(self):
        return list(self._pairs)


# ------------------------- 地址形态 -------------------------


@pytest.mark.parametrize(
    "serial,expected",
    [
        ("192.168.1.23:5555", True),
        ("10.0.0.2:41234", True),
        ("127.0.0.1:5555", True),
        ("343197069200106", False),  # 真机
        ("emulator-5554", False),  # 模拟器
        ("", False),
    ],
)
def test_is_network_serial(serial, expected):
    assert _is_network_serial(serial) is expected


# ------------------------- 连接结果解析 -------------------------


def test_connect_success_detected():
    adb = FakeAdb("connected to 192.168.1.23:5555")
    ok, out = adb.connect("192.168.1.23:5555")
    assert ok is True
    assert "connected to" in out


def test_connect_already_connected_counts_as_success():
    adb = FakeAdb("already connected to 192.168.1.23:5555")
    assert adb.connect("192.168.1.23:5555")[0] is True


def test_connect_failure_detected_despite_rc_zero():
    """adb connect 失败时也返回 0，只能靠输出文本判断——这是最容易漏的地方。"""
    adb = FakeAdb("cannot connect to 192.168.1.23:5555: No connection could be made")
    ok, _ = adb.connect("192.168.1.23:5555")
    assert ok is False


def test_connect_empty_output_is_failure():
    assert FakeAdb("").connect("1.2.3.4:5555")[0] is False


# ------------------------- 配对 -------------------------


def test_pair_success():
    adb = FakeAdb("Successfully paired to 192.168.1.23:41234")
    ok, _ = adb.pair("192.168.1.23:41234", "123456")
    assert ok is True
    assert adb.calls[-1] == ["pair", "192.168.1.23:41234", "123456"]


def test_pair_failure():
    adb = FakeAdb("Failed: Wrong password")
    assert adb.pair("192.168.1.23:41234", "000000")[0] is False


# ------------------------- 断线自动重连 -------------------------


def test_network_serial_reconnects_when_missing():
    """Wi-Fi 掉线后地址不在 devices 列表里，应自动 connect 而不是直接报错。"""
    adb = FakeAdb("connected to 192.168.1.23:5555", pairs=[("emulator-5554", "device")])
    serial, err = adb.ensure_device(serial="192.168.1.23:5555")
    assert (serial, err) == ("192.168.1.23:5555", "")


def test_network_serial_reports_when_reconnect_fails():
    adb = FakeAdb("cannot connect", pairs=[("emulator-5554", "device")])
    serial, err = adb.ensure_device(serial="192.168.1.23:5555")
    assert serial is None
    assert "192.168.1.23:5555" in err


def test_usb_serial_does_not_try_reconnect():
    """真机序列号掉了不该去 adb connect（那不是 IP，连不上还白等）。"""
    adb = FakeAdb("connected to x", pairs=[])
    serial, _err = adb.ensure_device(serial="343197069200106")
    assert serial is None
    assert not any("connect" in c for c in adb.calls)


# ------------------------- 配对后找连接端口 -------------------------


def test_after_pair_tries_5555_then_pair_port(monkeypatch, tmp_path):
    """Android 11+ 配对成功后 5555 常常没在监听，要按顺序试候选端口。

    真机现象：pair 用 37811 成功，connect 5555 得到「积极拒绝」。
    """
    attempts = []

    class Probe(FakeAdb):
        def connect(self, host_port):
            attempts.append(host_port)
            ok = host_port.endswith(":40001")  # 只有最后那个候选能连
            return ok, ("connected to " + host_port if ok else "cannot connect")

    monkeypatch.setattr("tools.qishui_auto.runner.local_config_path", lambda p: tmp_path / "q.json")
    adb = Probe()
    code = runner._after_pair(adb, "172.16.31.231:37811", tmp_path / "q.json", host="172.16.31.231:40001")
    assert code == EXIT_OK
    assert attempts == ["172.16.31.231:40001"]


def test_after_pair_guides_when_all_ports_fail(monkeypatch, tmp_path, capsys):
    class Probe(FakeAdb):
        def connect(self, host_port):
            return False, "cannot connect: refused"

    code = runner._after_pair(Probe(), "172.16.31.231:37811", tmp_path / "q.json", host=None)
    assert code == EXIT_RUNTIME
    out = capsys.readouterr().out
    # 必须告诉用户「配对端口和连接端口不同」，这是最容易被误导的地方
    assert "配对端口" in out and "连接端口" in out
    assert "--host" in out


# ------------------------- 记住的无线地址失效后回退 -------------------------


def test_stale_wifi_host_falls_back_to_usb():
    """无线调试关了、记住的地址失效时，插着 USB 必须还能跑。

    真实场景：wifi_host=172.16.31.231:39697 已失效，同时有 USB 设备在线。
    以前 apply_overrides 把它设成 serial（等于强制指定），直接报找不到设备。
    """
    adb = FakeAdb("cannot connect", pairs=[("6b14f005", "device")])
    serial, err = adb.ensure_device(prefer="172.16.31.231:39697")
    assert (serial, err) == ("6b14f005", "")


def test_prefer_used_when_online():
    adb = FakeAdb("", pairs=[("6b14f005", "device"), ("172.16.31.231:39697", "device")])
    serial, _ = adb.ensure_device(prefer="172.16.31.231:39697")
    assert serial == "172.16.31.231:39697"


def test_prefer_ignored_when_explicit_serial_given():
    """显式 --serial 仍然拥有最高优先级，找不到就报错不换设备。"""
    adb = FakeAdb("", pairs=[("6b14f005", "device")])
    serial, err = adb.ensure_device(serial="99999", prefer="6b14f005")
    assert serial is None
    assert "99999" in err


def test_usb_preferred_over_network_when_multiple_online():
    """多台在线时优先 USB：插着线通常就是此刻要用的那台。"""
    adb = FakeAdb("", pairs=[("172.16.25.70:5555", "device"), ("6b14f005", "device")])
    serial, err = adb.ensure_device()
    assert (serial, err) == ("6b14f005", "")


def test_two_usb_devices_still_ask():
    adb = FakeAdb("", pairs=[("6b14f005", "device"), ("other123", "device")])
    serial, err = adb.ensure_device()
    assert serial is None
    assert "--serial" in err
