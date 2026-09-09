"""设备探测：前台 App / 应用是否安装（ADB 只读命令）。"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from typing import Optional, Protocol, Sequence

from .client import MaaClientError

_PACKAGE_RE = re.compile(
    r"(?P<pkg>[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z0-9_]+)+)/[A-Za-z0-9_.$]+"
)
_FOCUS_KEYS = ("mCurrentFocus", "mFocusedApp", "mResumedActivity", "topResumedActivity")


class ShellRunner(Protocol):
    def run(self, args: Sequence[str], timeout: float = 10.0) -> str:
        ...


class SubprocessShellRunner:
    """通过 ``adb -s <address> ...`` 执行只读命令。"""

    def __init__(
        self,
        adb_path: str,
        address: Optional[str] = None,
        *,
        encoding: str = "utf-8",
        timeout: float = 10.0,
    ) -> None:
        self._adb_path = str(adb_path)
        self._address = address
        self._encoding = encoding
        self._timeout = timeout

    def run(self, args: Sequence[str], timeout: Optional[float] = None) -> str:
        command = [self._adb_path]
        if self._address:
            command += ["-s", self._address]
        command += list(args)
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding=self._encoding,
                errors="replace",
                timeout=timeout or self._timeout,
                check=False,
            )
        except FileNotFoundError as exc:
            raise MaaClientError(f"adb 不存在: {self._adb_path}") from exc
        except subprocess.TimeoutExpired as exc:
            raise MaaClientError(f"adb 命令超时: {' '.join(command)}") from exc
        return completed.stdout or ""


def parse_foreground_package(text: str) -> Optional[str]:
    """从 ``dumpsys window`` / ``dumpsys activity`` 输出解析前台包名。"""
    if not text:
        return None
    for key in _FOCUS_KEYS:
        for line in text.splitlines():
            if key not in line:
                continue
            match = _PACKAGE_RE.search(line)
            if match:
                return match.group("pkg")
    match = _PACKAGE_RE.search(text)
    return match.group("pkg") if match else None


@dataclass(frozen=True)
class ForegroundAppProbe:
    """查询当前前台 App 包名；失败返回 ``None``（不判任务失败）。"""

    shell: ShellRunner

    def probe(self) -> Optional[str]:
        for args in (
            ("shell", "dumpsys", "window", "windows"),
            ("shell", "dumpsys", "activity", "activities"),
        ):
            try:
                package = parse_foreground_package(self.shell.run(args))
            except MaaClientError:
                continue
            if package:
                return package
        return None


@dataclass(frozen=True)
class PackageProbe:
    """查询目标 App 是否安装；失败返回 ``None``。"""

    shell: ShellRunner

    def is_installed(self, package: str) -> Optional[bool]:
        try:
            output = self.shell.run(("shell", "pm", "list", "packages", package))
        except MaaClientError:
            return None
        if not output.strip():
            return False
        return f"package:{package}" in output


@dataclass(frozen=True)
class DeviceProbe:
    """前台 App + 安装状态组合探测。"""

    shell: ShellRunner

    def probe(self) -> Optional[str]:
        return ForegroundAppProbe(self.shell).probe()

    def is_installed(self, package: str) -> Optional[bool]:
        return PackageProbe(self.shell).is_installed(package)

