"""ADB 预检：连接设备并等待 Android 启动完成。

MAA 的 ADB 控制器会在连接阶段调用 ``adb -s <address> shell settings get
secure android_id``；如果模拟器刚启动、ADB 仍 offline，就会在 MAA 日志里
留下 ``child return error``。这里先做一次显式 connect + boot_completed
轮询，可显著减少这种噪声和连接失败。
"""

from __future__ import annotations

import subprocess
import time
from pathlib import Path
from typing import Optional, Sequence, Tuple


def _adb_command(adb_path: str, *args: str) -> list[str]:
    return [str(Path(adb_path)), *args]


def run_adb(
    adb_path: str,
    *args: str,
    timeout: float = 15.0,
) -> Optional[subprocess.CompletedProcess]:
    try:
        return subprocess.run(
            _adb_command(adb_path, *args),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None


def connect_device(adb_path: str, address: str, *, timeout: float = 15.0) -> bool:
    result = run_adb(adb_path, "connect", address, timeout=timeout)
    return result is not None and result.returncode == 0


def wait_for_boot(
    adb_path: str,
    address: str,
    *,
    timeout: float = 30.0,
) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        result = run_adb(
            adb_path,
            "-s",
            address,
            "shell",
            "getprop",
            "sys.boot_completed",
            timeout=10.0,
        )
        if (
            result is not None
            and result.returncode == 0
            and result.stdout.strip() == "1"
        ):
            return True
        time.sleep(1.0)
    return False


def ensure_device_ready(
    adb_path: str,
    address: str,
    *,
    timeout: float = 30.0,
) -> Tuple[bool, str]:
    """返回 (ready, 说明)。失败不抛异常，由调用方决定是否继续。"""
    if not adb_path.strip() or not address.strip():
        return False, "adb_path 或 address 为空"
    connected = connect_device(adb_path, address)
    ready = wait_for_boot(adb_path, address, timeout=timeout)
    if ready:
        return True, "设备已连接且 boot_completed=1"
    if connected:
        return False, "ADB 已连接但等待 boot_completed 超时"
    return False, "ADB connect 失败"


def _screencap_bytes(adb_path: str, address: str, *, timeout: float = 15.0) -> bytes:
    try:
        result = subprocess.run(
            _adb_command(adb_path, "-s", address, "exec-out", "screencap", "-p"),
            capture_output=True,
            timeout=timeout,
            check=False,
        )
        if result.returncode == 0:
            return result.stdout or b""
    except (OSError, subprocess.SubprocessError):
        pass
    return b""


def capture_ready(adb_path: str, address: str) -> bool:
    data = _screencap_bytes(adb_path, address)
    return data.startswith(b"\x89PNG") and len(data) > 1024


def current_focus(adb_path: str, address: str) -> str:
    result = run_adb(adb_path, "-s", address, "shell", "dumpsys", "window")
    if result is None:
        return ""
    for line in result.stdout.splitlines():
        if "mCurrentFocus" in line or "mFocusedApp" in line:
            return line.strip()
    return ""


def ensure_capture_ready(
    adb_path: str,
    address: str,
    *,
    package_name: str = "com.qq.reader",
    timeout: float = 30.0,
) -> Tuple[bool, str]:
    """确保当前页面可截图。

    QQ 阅读阅读页是 FLAG_SECURE，ADB screencap 会返回空；此时先退出/重启
    QQ 阅读回到可截图页面，否则 MAA 会报 ``No available screencap method``。
    """
    if capture_ready(adb_path, address):
        return True, "screencap 正常"
    focus = current_focus(adb_path, address)
    run_adb(adb_path, "-s", address, "shell", "am", "force-stop", package_name)
    time.sleep(1.0)
    run_adb(
        adb_path,
        "-s",
        address,
        "shell",
        "monkey",
        "-p",
        package_name,
        "-c",
        "android.intent.category.LAUNCHER",
        "1",
    )
    deadline = time.time() + timeout
    while time.time() < deadline:
        if capture_ready(adb_path, address):
            return True, "已退出安全页面/重启 QQ 阅读，screencap 正常"
        time.sleep(1.0)
    return False, f"screencap 仍为空（focus={focus or 'unknown'}）"


def ensure_maa_ready(
    adb_path: str,
    address: str,
    *,
    package_name: str = "com.qq.reader",
    timeout: float = 45.0,
) -> Tuple[bool, str]:
    ready, detail = ensure_device_ready(adb_path, address, timeout=timeout)
    if not ready:
        return False, detail
    return ensure_capture_ready(
        adb_path,
        address,
        package_name=package_name,
        timeout=timeout,
    )
