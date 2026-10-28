"""多模拟器发现与 ADB 地址探测（``qqreader.maa.emulator``）。

管理工具输出取自 2026-10-28 本机实测（只保留用到的字段）：
MuMu 12 ``MuMuManager info -v all``（实例 0 运行中）、雷电 9 ``ldconsole list2``。
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Dict, List, Sequence

import pytest

from qqreader.maa import emulator as emu

MUMU_INFO_ALL_RUNNING = json.dumps(
    {
        "0": {
            "index": "0", "name": "碧蓝航线", "is_android_started": True,
            "is_process_started": True, "adb_host_ip": "127.0.0.1", "adb_port": 16384,
            "is_main": True,
        },
        "1": {"index": "1", "name": "不思议迷宫", "is_android_started": False,
              "is_process_started": False, "is_main": False},
        "2": {"index": "2", "name": "MuMu模拟器12-2", "is_android_started": False,
              "is_process_started": False, "is_main": False},
    },
    ensure_ascii=False,
)
# 停止状态下的单实例输出（没有 adb_port）。
MUMU_INFO_ONE_STOPPED = json.dumps(
    {"index": "0", "name": "碧蓝航线", "is_android_started": False, "is_process_started": False},
    ensure_ascii=False,
)
LD_LIST2 = (
    "0,fire,0,0,0,-1,-1,1920,1080,320\n"
    "1,aknight,0,0,0,-1,-1,1280,720,240\n"
    "2,不思议迷宫,0,0,0,-1,-1,720,1280,320\n"
    "3,碧蓝档案,0,0,0,-1,-1,1280,720,240\n"
)
LD_LIST2_RUNNING = "2,不思议迷宫,132456,132460,1,4321,4400,720,1280,320\n"
BLUESTACKS_CONF = (
    'bst.instance.Pie64.status.adb_port="5555"\n'
    'bst.instance.Pie64_1.status.adb_port="5565"\n'
    'bst.instance.Pie64.display_name="BlueStacks"\n'
)


# ------------------------------------------------------------------ 解析


def test_parse_mumu_running_instance_has_port():
    instances = emu.parse_mumu_info(MUMU_INFO_ALL_RUNNING)
    assert [i.index for i in instances] == [0, 1, 2]
    first = instances[0]
    assert first.running and first.adb_address == "127.0.0.1:16384"
    assert first.name == "碧蓝航线"
    assert not instances[1].running and instances[1].adb_address is None


def test_parse_mumu_single_and_garbage():
    one = emu.parse_mumu_info(MUMU_INFO_ONE_STOPPED)
    assert len(one) == 1 and not one[0].running
    assert emu.parse_mumu_info("") == []
    assert emu.parse_mumu_info("[]") == []


def test_parse_ldconsole_list2_ports_and_resolution():
    instances = emu.parse_ldconsole_list2(LD_LIST2)
    assert [i.adb_address for i in instances] == [
        "127.0.0.1:5555", "127.0.0.1:5557", "127.0.0.1:5559", "127.0.0.1:5561"
    ]
    assert instances[0].resolution == (1920, 1080) and instances[0].density == 320
    assert instances[2].name == "不思议迷宫"
    assert not any(i.running for i in instances)
    assert emu.parse_ldconsole_list2(LD_LIST2_RUNNING)[0].running


def test_parse_bluestacks_conf():
    instances = emu.parse_bluestacks_conf(BLUESTACKS_CONF)
    assert [i.adb_address for i in instances] == ["127.0.0.1:5555", "127.0.0.1:5565"]


def test_parse_adb_devices():
    text = (
        "* daemon not running; starting now at tcp:5037\n"
        "List of devices attached\n"
        "127.0.0.1:16384\tdevice\n"
        "emulator-5554\tdevice\n"
        "127.0.0.1:5555\toffline\n\n"
    )
    assert emu.online_serials(text) == ["127.0.0.1:16384", "emulator-5554"]
    assert emu.serial_to_address("emulator-5554") == "127.0.0.1:5555"
    assert emu.serial_to_address("127.0.0.1:16384") == "127.0.0.1:16384"


@pytest.mark.parametrize(
    "path, kind",
    [
        (r"D:\Program Files\Netease\MuMu Player 12\shell\MuMuManager.exe", emu.KIND_MUMU),
        (r"C:\Program Files\Netease\MuMuPlayer-12.0\nx_main\adb.exe", emu.KIND_MUMU),
        (r"E:\leidian\LDPlayer9\ldconsole.exe", emu.KIND_LDPLAYER),
        (r"C:\LDPlayer\LDPlayer9\dnplayer.exe", emu.KIND_LDPLAYER),
        (r"C:\Program Files\BlueStacks_nxt\HD-Adb.exe", emu.KIND_BLUESTACKS),
        (r"D:\Program Files\Nox\bin\nox_adb.exe", emu.KIND_NOX),
        (r"D:\Microvirt\MEmu\adb.exe", emu.KIND_MEMU),
        (r"G:\platform-tools\adb.exe", None),
        (None, None),
    ],
)
def test_kind_from_path(path, kind):
    assert emu.kind_from_path(path) == kind


# ------------------------------------------------------------------ 安装目录


def _touch(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"")
    return path


def test_mumu_layouts_shell_and_nx_main(tmp_path):
    old = tmp_path / "MuMu Player 12"
    _touch(old / "shell" / "adb.exe")
    _touch(old / "shell" / "MuMuManager.exe")
    install = emu.installation_from_dir(emu.KIND_MUMU, old)
    assert install is not None and install.manager_path == old / "shell" / "MuMuManager.exe"

    new = tmp_path / "MuMuPlayer-12.0"
    _touch(new / "nx_main" / "adb.exe")
    _touch(new / "nx_main" / "MuMuManager.exe")
    # 注册表给的是 DisplayIcon（exe 路径）
    install = emu.installation_from_dir(emu.KIND_MUMU, _touch(new / "nx_main" / "MuMuNxMain.exe"))
    assert install is not None and install.adb_path == new / "nx_main" / "adb.exe"


def test_ldplayer_and_missing_adb(tmp_path):
    ld = tmp_path / "LDPlayer9"
    _touch(ld / "adb.exe")
    _touch(ld / "ldconsole.exe")
    install = emu.installation_from_dir(emu.KIND_LDPLAYER, ld / "dnplayer.exe")
    assert install is not None and install.manager_path == ld / "ldconsole.exe"
    assert emu.installation_from_dir(emu.KIND_NOX, tmp_path / "nothing") is None


def test_discover_dedupes_hint_and_registry(tmp_path, monkeypatch):
    monkeypatch.setattr(emu.shutil, "which", lambda name: None)
    shell = tmp_path / "MuMu Player 12" / "shell"
    _touch(shell / "adb.exe")
    _touch(shell / "MuMuManager.exe")
    ld = tmp_path / "LDPlayer9"
    _touch(ld / "adb.exe")
    _touch(ld / "ldconsole.exe")
    installs = emu.discover_installations(
        [str(shell / "MuMuManager.exe")],
        registry=lambda: [(emu.KIND_MUMU, shell / "MuMuPlayer.exe"), (emu.KIND_LDPLAYER, ld)],
        common=lambda: [],
    )
    assert [i.kind for i in installs] == [emu.KIND_MUMU, emu.KIND_LDPLAYER]


def test_discover_falls_back_to_default_install_dirs(tmp_path, monkeypatch):
    """2026-10-28 本机：MuMu 12 没有卸载注册项，注册表只找得到雷电。"""
    monkeypatch.setattr(emu.shutil, "which", lambda name: None)
    mumu = tmp_path / "Program Files" / "Netease" / "MuMu Player 12"
    _touch(mumu / "shell" / "adb.exe")
    _touch(mumu / "shell" / "MuMuManager.exe")
    ld = tmp_path / "leidian" / "LDPlayer9"
    _touch(ld / "adb.exe")
    _touch(ld / "ldconsole.exe")
    installs = emu.discover_installations(
        [],
        registry=lambda: [(emu.KIND_LDPLAYER, ld / "dnplayer.exe")],
        common=lambda: [(emu.KIND_MUMU, mumu), (emu.KIND_LDPLAYER, ld)],
    )
    assert sorted(i.kind for i in installs) == [emu.KIND_LDPLAYER, emu.KIND_MUMU]
    # 无偏好时 MuMu（标定环境）排第一，避免全新机器先拉起雷电
    assert emu.sort_installations(installs, None)[0].kind == emu.KIND_MUMU
    assert emu.sort_installations(installs, emu.KIND_LDPLAYER)[0].kind == emu.KIND_LDPLAYER


def test_common_dirs_cover_each_kind():
    kinds = {kind for kind, _ in emu.COMMON_INSTALL_DIRS}
    assert {emu.KIND_MUMU, emu.KIND_LDPLAYER, emu.KIND_BLUESTACKS, emu.KIND_NOX, emu.KIND_MEMU} <= kinds


# ------------------------------------------------------------------ 探测


class FakeAdb:
    """按命令行返回预设输出；``online`` 是 adb devices 里在线的地址集合。"""

    def __init__(self, outputs: Dict[str, str], online: Sequence[str] = ()):
        self.outputs = outputs
        self.online = set(online)
        self.calls: List[List[str]] = []

    def __call__(self, args, **kwargs):
        self.calls.append(list(args))
        exe = Path(args[0]).name.lower()
        rest = args[1:]
        stdout = ""
        if exe == "mumumanager.exe":
            stdout = self.outputs.get("mumu", "")
        elif exe == "ldconsole.exe":
            stdout = self.outputs.get("ld", "")
        elif rest[:1] == ["devices"]:
            stdout = "List of devices attached\n" + "".join(f"{s}\tdevice\n" for s in sorted(self.online))
        return subprocess.CompletedProcess(args, 0, stdout, "")


MUMU = emu.Installation(
    emu.KIND_MUMU, Path("C:/mumu/shell"), Path("C:/mumu/shell/adb.exe"), Path("C:/mumu/shell/MuMuManager.exe")
)
LD = emu.Installation(
    emu.KIND_LDPLAYER, Path("E:/ld"), Path("E:/ld/adb.exe"), Path("E:/ld/ldconsole.exe")
)


def _open_ports(*ports):
    return lambda host, port: port in ports


def test_configured_address_online_wins():
    fake = FakeAdb({"mumu": MUMU_INFO_ALL_RUNNING}, online=["127.0.0.1:16384"])
    result = emu.detect_device(
        configured_address="127.0.0.1:16384", installations=[MUMU], runner=fake,
        port_probe=_open_ports(16384),
    )
    assert result.found and result.address == "127.0.0.1:16384"
    assert result.kind == emu.KIND_MUMU and "配置" in result.source
    assert not any("MuMuManager.exe" in c[0] for c in fake.calls)


def test_port_drift_found_through_manager():
    """MuMu 端口漂移：配置里的 16384 不在线，管理工具报告实例 0 在 16416。"""
    info = MUMU_INFO_ALL_RUNNING.replace("16384", "16416")
    fake = FakeAdb({"mumu": info}, online=["127.0.0.1:16416"])
    result = emu.detect_device(
        configured_address="127.0.0.1:16384", installations=[MUMU], runner=fake,
        port_probe=_open_ports(16416),
    )
    assert result.address == "127.0.0.1:16416"
    assert "实例 0" in result.source


def test_ldplayer_running_instance_and_preferred_index():
    running = (
        "0,fire,1,1,1,100,101,1920,1080,320\n"
        "2,不思议迷宫,1,1,1,200,201,720,1280,320\n"
    )
    fake = FakeAdb({"ld": running}, online=["127.0.0.1:5555", "127.0.0.1:5559"])
    result = emu.detect_device(
        installations=[LD], runner=fake, index=2, port_probe=_open_ports(5555, 5559)
    )
    assert result.address == "127.0.0.1:5559" and result.kind == emu.KIND_LDPLAYER


def test_emulator_serial_from_adb_devices():
    fake = FakeAdb({"ld": LD_LIST2}, online=["emulator-5554"])
    result = emu.detect_device(installations=[LD], runner=fake, port_probe=_open_ports())
    assert result.address == "127.0.0.1:5555"
    assert "adb devices" in result.source


def test_default_port_scan_skips_closed_ports():
    plain = emu.Installation(emu.KIND_MEMU, Path("D:/memu"), Path("D:/memu/adb.exe"))
    fake = FakeAdb({}, online=[])

    class ConnectingAdb(FakeAdb):
        def __call__(self, args, **kwargs):
            if args[1:2] == ["connect"]:
                self.online.add(args[2])
            return super().__call__(args, **kwargs)

    fake = ConnectingAdb({})
    result = emu.detect_device(installations=[plain], runner=fake, port_probe=_open_ports(21513))
    assert result.address == "127.0.0.1:21513"
    connects = [c[2] for c in fake.calls if c[1:2] == ["connect"]]
    assert connects == ["127.0.0.1:21513"]


def test_nothing_online():
    fake = FakeAdb({"mumu": MUMU_INFO_ONE_STOPPED})
    result = emu.detect_device(installations=[MUMU], runner=fake, port_probe=_open_ports())
    assert not result.found
    assert any("没有在线设备" in note for note in result.notes)


def test_no_installation_at_all():
    result = emu.detect_device(installations=[], runner=FakeAdb({}))
    assert not result.found and "没有找到任何模拟器" in result.notes[0]


def test_launch_commands():
    fake = FakeAdb({})
    assert emu.launch_instance(MUMU, 1, runner=fake)
    assert emu.launch_instance(LD, 2, runner=fake)
    assert fake.calls[0][1:] == ["control", "-v", "1", "launch"]
    assert fake.calls[1][1:] == ["launch", "--index", "2"]
    assert not emu.launch_instance(emu.Installation(emu.KIND_NOX, Path("."), Path("adb.exe")), 0, runner=fake)


# ------------------------------------------------------------------ 配置


def _detection(adb="D:\\Program Files\\Netease\\MuMu Player 12\\shell\\adb.exe", address="127.0.0.1:16384"):
    install = emu.Installation(
        emu.KIND_MUMU, Path(adb).parent, Path(adb), Path(adb).parent / "MuMuManager.exe"
    )
    return emu.Detection(adb_path=adb, address=address, kind=emu.KIND_MUMU, installation=install)


def test_update_local_config_only_touches_adb_fields(tmp_path):
    path = tmp_path / "qqreader.local.json"
    original = {
        "version": 1,
        "machine": {
            "adb_path": "D:/Program Files/Netease/MuMu Player 12/shell/adb.exe",
            "adb_address": "127.0.0.1:16384",
            "emulator_path": "D:/Program Files/Netease/MuMu Player 12/shell/MuMuManager.exe",
            "maa_short_side": 720,
        },
        "captcha": {"solver": "slide"},
    }
    path.write_text(json.dumps(original), encoding="utf-8")
    before = path.read_bytes()
    # 只是斜杠不同：不改写文件
    assert emu.update_local_config(path, _detection()) is False
    assert path.read_bytes() == before

    assert emu.update_local_config(path, _detection(address="127.0.0.1:16416")) is True
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["machine"]["adb_address"] == "127.0.0.1:16416"
    assert data["machine"]["maa_short_side"] == 720
    assert data["captcha"] == {"solver": "slide"}


def test_init_local_config_from_example(tmp_path):
    repo = tmp_path / "repo"
    example = Path(__file__).resolve().parents[1] / "configs" / "qqreader.example.json"
    _touch(repo / "dev" / "MaaFramework.dll")
    target = repo / "configs" / "qqreader.local.json"
    emu.init_local_config(target, example, _detection(), python="C:/py/python.exe")
    machine = json.loads(target.read_text(encoding="utf-8"))["machine"]
    assert machine["adb_address"] == "127.0.0.1:16384"
    assert machine["python_executable"] == "C:/py/python.exe"
    assert machine["maa_runtime_dir"] == "../dev"
    assert machine["record_dir"] == "../runtime/records"
    assert machine["emulator_path"].endswith("MuMuManager.exe")

    from qqreader.config import load_config

    config = load_config(target)
    assert config.machine.maa_runtime_dir == (repo / "configs" / "../dev")


def test_ldconsole_decoded_with_ansi_code_page_even_in_utf8_mode(monkeypatch):
    """启动器设了 PYTHONUTF8=1；ldconsole 输出 GBK，按 UTF-8 解会把实例名变成乱码（10-28 实测）。"""
    seen = {}

    def runner(args, **kwargs):
        seen["encoding"] = kwargs.get("encoding")
        raw = LD_LIST2.encode("gbk")
        return subprocess.CompletedProcess(args, 0, raw.decode(kwargs["encoding"], "replace"), "")

    monkeypatch.setattr(emu, "ansi_encoding", lambda: "cp936")
    instances = emu.list_instances(LD, runner=runner)
    assert seen["encoding"] == "cp936"
    assert instances[2].name == "不思议迷宫"
