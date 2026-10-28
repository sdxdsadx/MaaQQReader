"""模拟器发现与 ADB 地址探测（多模拟器、多实例、不写死路径和端口）。

支持：MuMu 12、雷电 9（LDPlayer）、BlueStacks 5、夜神、逍遥，以及任何已经
``adb devices`` 可见的设备（真机 / 其他模拟器）。

探测顺序：
1. 配置里的 ``adb_address`` 已在线 → 直接用；
2. 模拟器管理工具（MuMuManager / ldconsole）报告的运行中实例；
3. ``adb devices`` 里已在线的设备；
4. 各模拟器的默认端口逐个 ``adb connect``。

命令行（启动器调用）::

    python -m qqreader.maa.emulator detect  [--config PATH]
    python -m qqreader.maa.emulator prepare --config PATH [--launch] [--index N]

``prepare`` 会在需要时拉起模拟器、等 Android 启动完成、检查分辨率，并把
``adb_path`` / ``adb_address`` / ``emulator_path`` 写回本机配置（只改这三项）。
"""

from __future__ import annotations

import argparse
import json
import locale
import os
import re
import shutil
import socket
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

KIND_MUMU = "mumu12"
KIND_LDPLAYER = "ldplayer"
KIND_BLUESTACKS = "bluestacks5"
KIND_NOX = "nox"
KIND_MEMU = "memu"
KIND_GENERIC = "adb"

KIND_LABELS = {
    KIND_MUMU: "MuMu 模拟器 12",
    KIND_LDPLAYER: "雷电模拟器",
    KIND_BLUESTACKS: "BlueStacks 5",
    KIND_NOX: "夜神模拟器",
    KIND_MEMU: "逍遥模拟器",
    KIND_GENERIC: "ADB 设备",
}

#: 未运行管理工具时逐个尝试的默认端口（实例 0 在前）。
DEFAULT_PORTS: Dict[str, Tuple[int, ...]] = {
    KIND_MUMU: tuple(16384 + 32 * i for i in range(8)) + (7555,),
    KIND_LDPLAYER: tuple(5555 + 2 * i for i in range(8)),
    KIND_BLUESTACKS: tuple(5555 + 10 * i for i in range(8)),
    KIND_NOX: (62001,) + tuple(62025 + i for i in range(7)),
    KIND_MEMU: tuple(21503 + 10 * i for i in range(8)),
}

Runner = Callable[..., "subprocess.CompletedProcess[str]"]
PortProbe = Callable[[str, int], bool]


def port_open(host: str, port: int, timeout: float = 0.3) -> bool:
    """TCP 端口是否在监听。Windows 上 adb connect 一个关闭的端口要等约 2 秒，先用它筛。"""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _split_address(address: str) -> Optional[Tuple[str, int]]:
    host, sep, port = address.rpartition(":")
    if not sep or not port.isdigit():
        return None
    return host or "127.0.0.1", int(port)


@dataclass(frozen=True)
class Installation:
    """一个已安装的模拟器（或一个独立 adb）。"""

    kind: str
    root: Path
    adb_path: Optional[Path]
    manager_path: Optional[Path] = None

    @property
    def label(self) -> str:
        return KIND_LABELS.get(self.kind, self.kind)


@dataclass(frozen=True)
class Instance:
    """模拟器管理工具报告的一个实例。"""

    kind: str
    index: int
    name: str = ""
    running: bool = False
    adb_address: Optional[str] = None
    resolution: Optional[Tuple[int, int]] = None
    density: Optional[int] = None


@dataclass
class Detection:
    """探测结果：选中的设备 + 过程记录（用于排障输出）。"""

    adb_path: Optional[str] = None
    address: Optional[str] = None
    kind: Optional[str] = None
    source: str = ""
    installation: Optional[Installation] = None
    notes: List[str] = field(default_factory=list)

    @property
    def found(self) -> bool:
        return bool(self.adb_path and self.address)


# ---------------------------------------------------------------- 解析 ----


def parse_adb_devices(text: str) -> List[Tuple[str, str]]:
    """解析 ``adb devices`` 输出，返回 [(serial, state), ...]。"""
    devices = []
    for line in (text or "").splitlines():
        line = line.strip()
        if not line or line.startswith("List of devices") or line.startswith("*"):
            continue
        parts = line.split()
        if len(parts) >= 2:
            devices.append((parts[0], parts[1]))
    return devices


def online_serials(text: str) -> List[str]:
    return [serial for serial, state in parse_adb_devices(text) if state == "device"]


def _bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("1", "true", "yes")


def parse_mumu_info(text: str) -> List[Instance]:
    """解析 ``MuMuManager info -v all``（或 ``-v N``）的 JSON 输出。"""
    try:
        data = json.loads(text or "")
    except json.JSONDecodeError:
        return []
    if not isinstance(data, dict):
        return []
    entries = [data] if "index" in data else [v for v in data.values() if isinstance(v, dict)]
    instances = []
    for entry in entries:
        try:
            index = int(entry.get("index"))
        except (TypeError, ValueError):
            continue
        running = _bool(entry.get("is_android_started")) or _bool(entry.get("is_process_started"))
        address = None
        port = entry.get("adb_port")
        if port not in (None, ""):
            host = entry.get("adb_host_ip") or "127.0.0.1"
            address = f"{host}:{int(port)}"
        instances.append(
            Instance(
                kind=KIND_MUMU,
                index=index,
                name=str(entry.get("name") or ""),
                running=running,
                adb_address=address,
            )
        )
    return sorted(instances, key=lambda item: item.index)


def parse_ldconsole_list2(text: str) -> List[Instance]:
    """解析 ``ldconsole list2``：index,title,top_hwnd,bind_hwnd,android_started,pid,vbox_pid,w,h,dpi。"""
    instances = []
    for line in (text or "").splitlines():
        parts = [part.strip() for part in line.split(",")]
        if len(parts) < 10:
            continue
        try:
            index = int(parts[0])
            started = int(parts[4]) == 1
            width, height, dpi = int(parts[7]), int(parts[8]), int(parts[9])
        except ValueError:
            continue
        instances.append(
            Instance(
                kind=KIND_LDPLAYER,
                index=index,
                name=parts[1],
                running=started,
                adb_address=f"127.0.0.1:{5555 + 2 * index}",
                resolution=(width, height),
                density=dpi,
            )
        )
    return instances


def parse_bluestacks_conf(text: str) -> List[Instance]:
    """解析 BlueStacks 5 的 ``bluestacks.conf``，取各实例的 ``adb_port``。"""
    instances = []
    pattern = re.compile(r'^bst\.instance\.([^.]+)\.status\.adb_port="?(\d+)"?', re.M)
    for i, (name, port) in enumerate(pattern.findall(text or "")):
        instances.append(
            Instance(kind=KIND_BLUESTACKS, index=i, name=name, adb_address=f"127.0.0.1:{port}")
        )
    return instances


def serial_to_address(serial: str) -> str:
    """``emulator-5554`` → ``127.0.0.1:5555``（雷电 / 原生模拟器的控制台串号）。"""
    match = re.fullmatch(r"emulator-(\d+)", serial)
    if match:
        return f"127.0.0.1:{int(match.group(1)) + 1}"
    return serial


def kind_from_path(path: Optional[str]) -> Optional[str]:
    """根据 ``emulator_path`` / ``adb_path`` 判断模拟器类型。"""
    if not path:
        return None
    text = str(path).replace("/", "\\").lower()
    if "mumu" in text or "netease" in text:
        return KIND_MUMU
    if "ldplayer" in text or "leidian" in text or text.endswith(("ldconsole.exe", "dnplayer.exe")):
        return KIND_LDPLAYER
    if "bluestacks" in text or text.endswith("hd-adb.exe"):
        return KIND_BLUESTACKS
    if "nox" in text:
        return KIND_NOX
    if "memu" in text or "microvirt" in text:
        return KIND_MEMU
    return None


# ---------------------------------------------------------------- 安装 ----


def _first_existing(root: Path, names: Sequence[str]) -> Optional[Path]:
    for name in names:
        candidate = root / name
        if candidate.is_file():
            return candidate
    return None


def installation_from_dir(kind: str, root: Path) -> Optional[Installation]:
    """在安装目录里找 adb 与管理工具；找不到 adb 返回 None。"""
    root = Path(root)
    if root.is_file() or root.suffix.lower() == ".exe":
        root = root.parent
    if kind == KIND_MUMU:
        # MuMu 12：<安装目录>\shell\（旧版）或 <安装目录>\nx_main\（4.x 起）
        for base in (root, root / "shell", root / "nx_main", root.parent / "shell", root.parent / "nx_main"):
            manager = _first_existing(base, ("MuMuManager.exe",))
            adb = _first_existing(base, ("adb.exe",))
            if adb:
                return Installation(kind, base, adb, manager)
        return None
    if kind == KIND_LDPLAYER:
        adb = _first_existing(root, ("adb.exe",))
        manager = _first_existing(root, ("ldconsole.exe", "dnconsole.exe"))
        return Installation(kind, root, adb, manager) if adb else None
    if kind == KIND_BLUESTACKS:
        adb = _first_existing(root, ("HD-Adb.exe",))
        return Installation(kind, root, adb) if adb else None
    if kind == KIND_NOX:
        for base in (root, root / "bin"):
            adb = _first_existing(base, ("nox_adb.exe", "adb.exe"))
            if adb:
                return Installation(kind, base, adb)
        return None
    if kind == KIND_MEMU:
        adb = _first_existing(root, ("adb.exe",))
        return Installation(kind, root, adb, _first_existing(root, ("memuc.exe",))) if adb else None
    adb = _first_existing(root, ("adb.exe",))
    return Installation(KIND_GENERIC, root, adb) if adb else None


def _registry_install_dirs() -> List[Tuple[str, Path]]:  # pragma: no cover - 依赖本机注册表
    """从 Windows 卸载信息里找模拟器安装目录。"""
    try:
        import winreg
    except ImportError:
        return []
    found: List[Tuple[str, Path]] = []
    roots = (
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
    )
    for hive, path in roots:
        try:
            key = winreg.OpenKey(hive, path)
        except OSError:
            continue
        with key:
            for i in range(winreg.QueryInfoKey(key)[0]):
                try:
                    name = winreg.EnumKey(key, i)
                    with winreg.OpenKey(key, name) as sub:
                        values = {}
                        for field_name in ("DisplayIcon", "InstallLocation", "UninstallString", "DisplayName"):
                            try:
                                values[field_name] = str(winreg.QueryValueEx(sub, field_name)[0])
                            except OSError:
                                pass
                except OSError:
                    continue
                text = " ".join([name, *values.values()])
                kind = kind_from_path(text)
                if kind is None:
                    continue
                raw = values.get("InstallLocation") or values.get("DisplayIcon") or values.get("UninstallString") or ""
                raw = raw.split(",")[0].strip().strip('"')
                if raw:
                    found.append((kind, Path(raw)))
    try:  # BlueStacks 5 自己的键
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\BlueStacks_nxt") as key:
            found.append((KIND_BLUESTACKS, Path(str(winreg.QueryValueEx(key, "InstallDir")[0]))))
    except OSError:
        pass
    return found


#: 各模拟器的默认安装目录（相对盘符根）。有的安装方式不写卸载注册项
#: （2026-10-28 本机 MuMu 12 即是如此），只能按默认目录找。
COMMON_INSTALL_DIRS: Tuple[Tuple[str, str], ...] = (
    (KIND_MUMU, r"Program Files\Netease\MuMu Player 12"),
    (KIND_MUMU, r"Program Files\Netease\MuMuPlayer-12.0"),
    (KIND_MUMU, r"Program Files\Netease\MuMu"),
    (KIND_LDPLAYER, r"leidian\LDPlayer9"),
    (KIND_LDPLAYER, r"LDPlayer\LDPlayer9"),
    (KIND_BLUESTACKS, r"Program Files\BlueStacks_nxt"),
    (KIND_NOX, r"Program Files\Nox\bin"),
    (KIND_NOX, r"Program Files (x86)\Nox\bin"),
    (KIND_MEMU, r"Program Files\Microvirt\MEmu"),
)

#: 没有任何偏好时的选择顺序（MuMu 12 是标定环境）。
KIND_PRIORITY = (KIND_MUMU, KIND_LDPLAYER, KIND_BLUESTACKS, KIND_NOX, KIND_MEMU, KIND_GENERIC)


def _common_install_dirs() -> List[Tuple[str, Path]]:  # pragma: no cover - 依赖本机磁盘
    found = []
    for letter in "CDEFGHIJ":
        drive = Path(f"{letter}:/")
        if not drive.exists():
            continue
        for kind, rel in COMMON_INSTALL_DIRS:
            path = drive / rel
            if path.is_dir():
                found.append((kind, path))
    return found


def sort_installations(installs: List[Installation], preferred: Optional[str]) -> List[Installation]:
    """偏好的模拟器排最前，其余按 :data:`KIND_PRIORITY`。"""

    def key(item: Installation) -> Tuple[int, int]:
        rank = KIND_PRIORITY.index(item.kind) if item.kind in KIND_PRIORITY else len(KIND_PRIORITY)
        return (0 if item.kind == preferred else 1, rank)

    return sorted(installs, key=key)


def discover_installations(
    hints: Iterable[Optional[str]] = (),
    *,
    registry: Optional[Callable[[], List[Tuple[str, Path]]]] = None,
    common: Optional[Callable[[], List[Tuple[str, Path]]]] = None,
) -> List[Installation]:
    """配置里的路径优先，其次注册表，再次默认安装目录；同一目录只保留一次。"""
    candidates: List[Tuple[str, Path]] = []
    for hint in hints:
        kind = kind_from_path(hint)
        if hint:
            candidates.append((kind or KIND_GENERIC, Path(str(hint))))
    candidates.extend((registry or _registry_install_dirs)())
    candidates.extend((common or _common_install_dirs)())
    result: List[Installation] = []
    seen = set()
    for kind, path in candidates:
        try:
            install = installation_from_dir(kind, path)
        except OSError:
            install = None
        if install is None or install.adb_path is None:
            continue
        key = (install.kind, str(install.adb_path).lower())
        if key in seen:
            continue
        seen.add(key)
        result.append(install)
    path_adb = shutil.which("adb")
    if path_adb and not any(str(i.adb_path).lower() == path_adb.lower() for i in result):
        result.append(Installation(KIND_GENERIC, Path(path_adb).parent, Path(path_adb)))
    return result


# ---------------------------------------------------------------- 探测 ----


def _run(
    runner: Runner, args: Sequence[str], timeout: float = 15.0, *, encoding: str = "utf-8"
) -> str:
    try:
        result = runner(
            list(args),
            capture_output=True,
            text=True,
            encoding=encoding,
            errors="replace",
            timeout=timeout,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.SubprocessError, ValueError):
        return ""
    return result.stdout or ""


def ansi_encoding() -> str:
    """系统 ANSI 代码页（中文 Windows 是 cp936）。ldconsole 按它输出。

    启动器设了 ``PYTHONUTF8=1``，此时 ``locale.getpreferredencoding()`` 返回 UTF-8，不能用。
    """
    try:
        import ctypes

        return f"cp{ctypes.windll.kernel32.GetACP()}"
    except (AttributeError, OSError):
        return locale.getpreferredencoding(False) or "utf-8"


def list_instances(install: Installation, runner: Runner = subprocess.run) -> List[Instance]:
    """向模拟器管理工具查询实例；没有管理工具时返回空列表。"""
    if install.kind == KIND_MUMU and install.manager_path:
        return parse_mumu_info(_run(runner, [str(install.manager_path), "info", "-v", "all"]))
    if install.kind == KIND_LDPLAYER and install.manager_path:
        return parse_ldconsole_list2(
            _run(runner, [str(install.manager_path), "list2"], encoding=ansi_encoding())
        )
    if install.kind == KIND_BLUESTACKS:
        for conf in (
            Path(os.environ.get("ProgramData", r"C:\ProgramData")) / "BlueStacks_nxt" / "bluestacks.conf",
            install.root / "bluestacks.conf",
        ):
            if conf.is_file():
                return parse_bluestacks_conf(conf.read_text(encoding="utf-8", errors="replace"))
    return []


def is_online(
    adb_path: str,
    address: str,
    runner: Runner = subprocess.run,
    *,
    port_probe: PortProbe = port_open,
) -> bool:
    endpoint = _split_address(address)
    if endpoint is not None:
        if not port_probe(*endpoint):
            return False
        _run(runner, [adb_path, "connect", address], timeout=10.0)
    serials = online_serials(_run(runner, [adb_path, "devices"]))
    return address in serials or any(serial_to_address(s) == address for s in serials)


def detect_device(
    *,
    configured_address: Optional[str] = None,
    configured_adb: Optional[str] = None,
    emulator_path: Optional[str] = None,
    index: Optional[int] = None,
    installations: Optional[Sequence[Installation]] = None,
    runner: Runner = subprocess.run,
    port_probe: PortProbe = port_open,
    scan_default_ports: bool = True,
) -> Detection:
    """按「配置 → 管理工具 → adb devices → 默认端口」的顺序找一个在线设备。"""
    detection = Detection()
    installs = list(
        installations
        if installations is not None
        else discover_installations((emulator_path, configured_adb))
    )
    preferred_kind = kind_from_path(emulator_path) or kind_from_path(configured_adb)
    installs = sort_installations(installs, preferred_kind)
    if not installs:
        detection.notes.append("没有找到任何模拟器或 adb；请安装模拟器，或在配置里填写 adb_path")
        return detection
    for install in installs:
        detection.notes.append(f"发现 {install.label}: {install.adb_path}")

    def choose(install: Installation, address: str, source: str) -> Detection:
        detection.adb_path = str(install.adb_path)
        detection.address = address
        detection.kind = install.kind
        detection.installation = install
        detection.source = source
        detection.notes.append(f"选用 {install.label} {address}（{source}）")
        return detection

    # 1) 配置里的地址已在线
    if configured_address:
        for install in installs:
            if is_online(str(install.adb_path), configured_address, runner, port_probe=port_probe):
                return choose(install, configured_address, "配置中的地址在线")
        detection.notes.append(f"配置地址 {configured_address} 不在线")

    # 2) 管理工具报告的运行中实例（指定 index 时优先它）
    for install in installs:
        instances = [i for i in list_instances(install, runner) if i.running and i.adb_address]
        instances.sort(key=lambda i: (0 if index is not None and i.index == index else 1, i.index))
        for inst in instances:
            if is_online(str(install.adb_path), str(inst.adb_address), runner, port_probe=port_probe):
                return choose(
                    install, str(inst.adb_address), f"{install.label} 实例 {inst.index}「{inst.name}」运行中"
                )

    # 3) adb devices 里已在线的设备
    for install in installs:
        serials = online_serials(_run(runner, [str(install.adb_path), "devices"]))
        if serials:
            return choose(install, serial_to_address(serials[0]), "adb devices 已在线")

    # 4) 默认端口
    if scan_default_ports:
        for install in installs:
            ports = [p for p in DEFAULT_PORTS.get(install.kind, ()) if port_probe("127.0.0.1", p)]
            if not ports:
                continue
            adb = str(install.adb_path)
            for port in ports:
                _run(runner, [adb, "connect", f"127.0.0.1:{port}"], timeout=5.0)
            serials = set(online_serials(_run(runner, [adb, "devices"])))
            for port in ports:
                address = f"127.0.0.1:{port}"
                if address in serials:
                    return choose(install, address, f"{install.label} 默认端口")
    detection.notes.append("没有在线设备：模拟器可能未启动")
    return detection


def launch_instance(install: Installation, index: int, runner: Runner = subprocess.run) -> bool:
    """用模拟器自带管理工具启动实例；不支持的模拟器返回 False（请手动启动）。"""
    if not install.manager_path:
        return False
    if install.kind == KIND_MUMU:
        _run(runner, [str(install.manager_path), "control", "-v", str(index), "launch"], timeout=60.0)
        return True
    if install.kind == KIND_LDPLAYER:
        _run(runner, [str(install.manager_path), "launch", "--index", str(index)], timeout=60.0)
        return True
    if install.kind == KIND_MEMU:
        _run(runner, [str(install.manager_path), "start", "-i", str(index)], timeout=60.0)
        return True
    return False


# ---------------------------------------------------------------- 配置 ----


def update_local_config(path: Path, detection: Detection) -> bool:
    """只回写 adb_path / adb_address / emulator_path；未变化时不写文件。"""
    path = Path(path)
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    machine = data.setdefault("machine", {})
    updates = {"adb_path": detection.adb_path, "adb_address": detection.address}
    install = detection.installation
    if install is not None and install.manager_path is not None:
        updates["emulator_path"] = str(install.manager_path)
    changed = False
    for key, value in updates.items():
        current = machine.get(key)
        if not value or (isinstance(current, str) and _same_setting(key, current, value)):
            continue
        if current != value:
            machine[key] = value
            changed = True
    if changed:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return changed


def init_local_config(path: Path, example: Path, detection: Detection, *, python: str = "") -> None:
    """全新机器：按示例配置生成本机配置，填入探测到的 adb、当前 Python 与仓库内的 Maa 运行时。

    相对目录按配置文件所在目录解析（见 ``MachineConfig.resolve_paths``），所以运行目录
    写成 ``../runtime/...``，整个目录搬到别处仍可用。
    """
    path = Path(path)
    data = json.loads(Path(example).read_text(encoding="utf-8-sig"))
    machine = data.setdefault("machine", {})
    root = path.resolve().parent.parent
    machine.update(
        screenshot_dir="../runtime/screenshots",
        log_dir="../runtime/logs",
        record_dir="../runtime/records",
        python_executable=python or sys.executable,
        emulator_path=None,
    )
    dev = root / "dev"
    if (dev / "MaaFramework.dll").is_file():
        machine.update(
            maa_runtime_dir="../dev",
            maa_resource_dir="../dev/resource",
            maa_agent_dir="../dev/MaaAgentBinary",
        )
    if detection.found:
        machine["adb_path"] = detection.adb_path
        machine["adb_address"] = detection.address
        if detection.installation is not None and detection.installation.manager_path is not None:
            machine["emulator_path"] = str(detection.installation.manager_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _same_setting(key: str, current: str, value: str) -> bool:
    """路径只是斜杠或大小写不同时视为相同，避免每次启动都改写配置。"""
    if key == "adb_address":
        return current.strip() == value.strip()
    return os.path.normcase(os.path.normpath(current)) == os.path.normcase(os.path.normpath(value))


def _read_machine(path: Optional[Path]) -> Mapping[str, object]:
    if path is None or not Path(path).is_file():
        return {}
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return {}
    machine = data.get("machine") if isinstance(data, dict) else None
    return machine if isinstance(machine, dict) else {}


def _print(message: str) -> None:
    print(message, flush=True)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m qqreader.maa.emulator", description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=("detect", "prepare"))
    parser.add_argument("--config", type=Path, help="本机配置（configs/qqreader.local.json）")
    parser.add_argument("--index", type=int, default=None, help="模拟器实例序号（默认取环境变量 QQREADER_EMULATOR_INDEX，否则 0）")
    parser.add_argument("--launch", action="store_true", help="没有在线设备时用模拟器管理工具拉起实例")
    parser.add_argument("--wait-seconds", type=float, default=180.0)
    parser.add_argument("--example", type=Path, help="本机配置不存在时，以此示例配置生成（prepare）")
    args = parser.parse_args(argv)

    index = args.index
    if index is None:
        try:
            index = int(os.environ.get("QQREADER_EMULATOR_INDEX", "0"))
        except ValueError:
            index = 0
    machine = _read_machine(args.config)
    kwargs = dict(
        configured_address=str(machine.get("adb_address") or "") or None,
        configured_adb=str(machine.get("adb_path") or "") or None,
        emulator_path=str(machine.get("emulator_path") or "") or None,
        index=index,
    )
    detection = detect_device(**kwargs)
    if not detection.found and args.command == "prepare" and args.launch:
        installs = discover_installations((kwargs["emulator_path"], kwargs["configured_adb"]))
        preferred = kind_from_path(kwargs["emulator_path"]) or kind_from_path(kwargs["configured_adb"])
        installs = sort_installations(installs, preferred)
        for install in installs:
            if launch_instance(install, index):
                _print(f"[env] 正在启动 {install.label} 实例 {index} ...")
                deadline = time.time() + args.wait_seconds
                while time.time() < deadline:
                    time.sleep(3.0)
                    detection = detect_device(installations=[install], index=index, scan_default_ports=False, **{
                        k: v for k, v in kwargs.items() if k not in ("index",)
                    })
                    if detection.found:
                        break
                break
    for note in detection.notes:
        _print(f"[env] {note}")
    if not detection.found:
        _print("[warn] 未找到在线的模拟器/设备，GUI 内连接时还会重试。")
        if args.command == "prepare" and args.config is not None and not Path(args.config).is_file():
            if args.example is not None and Path(args.example).is_file():
                init_local_config(Path(args.config), Path(args.example), detection)
                _print(f"[env] 已按示例生成 {args.config}；adb_path / adb_address 仍是占位值，请填写或启动模拟器后重新运行")
        return 1

    from .adb import wait_for_boot
    from .display import check_device_display

    if args.command == "prepare":
        if wait_for_boot(str(detection.adb_path), str(detection.address), timeout=args.wait_seconds):
            _print("[env] Android 已启动完成。")
        else:
            _print("[warn] 等待 boot_completed 超时，仍继续。")
    assessment = check_device_display(str(detection.adb_path), str(detection.address))
    _print(f"[env] 分辨率检查: {assessment.render()}")
    if args.command == "prepare" and args.config is not None and not Path(args.config).is_file():
        if args.example is not None and Path(args.example).is_file():
            init_local_config(Path(args.config), Path(args.example), detection)
            _print(f"[env] 未找到本机配置，已按示例生成 {args.config}；请核对 Maa 运行时目录与 python_executable")
    elif args.command == "prepare" and args.config is not None:
        if update_local_config(Path(args.config), detection):
            _print(f"[env] 已更新配置 adb_path / adb_address -> {detection.adb_path} {detection.address}")
        else:
            _print("[env] 配置中的 adb 设置与实际一致。")
    _print(f"ADB_PATH={detection.adb_path}")
    _print(f"ADB_ADDRESS={detection.address}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
