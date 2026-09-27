"""模拟器地址选择（纯逻辑，不依赖 Tkinter）。

GUI 选中的地址保存在 ``runtime/gui_device.json``，运行任务时通过环境变量
``QQREADER_ADB_ADDRESS`` 传给子进程（配置加载器支持该覆盖），而不是改写
``configs/qqreader.local.json``：启动脚本每次都会把 MuMu 实例 0 的端口写回
配置，直接改配置会被下一次启动覆盖。
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

ADB_ADDRESS_ENV = "QQREADER_ADB_ADDRESS"
#: MuMu 12 多开实例的默认 ADB 端口：16384 + 32 × 实例序号。
MUMU_BASE_PORT = 16384
MUMU_PORT_STEP = 32
MUMU_SCAN_INSTANCES = 4

_HOST_PORT = re.compile(r"^[A-Za-z0-9.\-]+:(\d{1,5})$")
_SERIAL = re.compile(r"^[A-Za-z0-9._:\-]+$")


def mumu_default_addresses(count: int = MUMU_SCAN_INSTANCES) -> List[str]:
    return [f"127.0.0.1:{MUMU_BASE_PORT + MUMU_PORT_STEP * index}" for index in range(count)]


def validate_address(raw: str) -> str:
    """校验并返回规范化的地址；支持 ``host:port`` 和 ``emulator-5554`` 这类序列号。"""
    text = (raw or "").strip()
    if not text:
        raise ValueError("模拟器地址不能为空")
    match = _HOST_PORT.match(text)
    if match:
        port = int(match.group(1))
        if not 1 <= port <= 65535:
            raise ValueError(f"端口超出范围: {port}")
        return text
    if ":" in text or not _SERIAL.match(text):
        raise ValueError(f"无法识别的模拟器地址: {text!r}（示例 127.0.0.1:16384）")
    return text


def parse_adb_devices(output: str) -> List[Tuple[str, str]]:
    """解析 ``adb devices`` 输出，返回 [(序列号, 状态)]。"""
    devices: List[Tuple[str, str]] = []
    for line in (output or "").splitlines():
        line = line.strip()
        if not line or line.startswith("List of devices") or line.startswith("*"):
            continue
        parts = line.split()
        if len(parts) >= 2:
            devices.append((parts[0], parts[1]))
    return devices


def candidate_addresses(
    configured: str,
    devices: Iterable[Tuple[str, str]] = (),
    *,
    saved: str = "",
    extra: Sequence[str] = (),
) -> List[str]:
    """下拉框候选：已选 → 配置 → 在线设备 → 其他候选，去重保序。"""
    ordered: List[str] = []
    for address in (saved, configured):
        if address:
            ordered.append(address)
    ordered.extend(serial for serial, state in devices if state == "device")
    ordered.extend(extra)
    result: List[str] = []
    for address in ordered:
        address = address.strip()
        if address and address not in result:
            result.append(address)
    return result


def describe_devices(devices: Iterable[Tuple[str, str]]) -> str:
    items = [f"{serial}（{'在线' if state == 'device' else state}）" for serial, state in devices]
    return "、".join(items) if items else "无"


def load_device_address(path: Path) -> str:
    """读取 GUI 上次选择的地址；文件不存在或损坏时返回空串（跟随配置）。"""
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ""
    value = raw.get("adb_address") if isinstance(raw, dict) else None
    if not isinstance(value, str):
        return ""
    try:
        return validate_address(value)
    except ValueError:
        return ""


def save_device_address(path: Path, address: str) -> None:
    """保存 GUI 选择；传空串表示恢复为跟随配置文件。"""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {"adb_address": validate_address(address) if address else ""}
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def child_env(base: Mapping[str, str], address: str) -> Dict[str, str]:
    """子进程环境：有 GUI 选择时覆盖 ADB 地址，否则原样继承。"""
    env = dict(base)
    if address:
        env[ADB_ADDRESS_ENV] = address
    return env


def effective_address(configured: str, override: Optional[str]) -> str:
    return override or configured
