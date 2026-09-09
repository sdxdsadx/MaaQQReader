"""GUI 可测试的纯命令/参数逻辑（不依赖 Tkinter）。"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Sequence, Tuple


def build_run_game_flow_command(
    python_executable: str,
    repo_root: Path,
    config_path: Path,
    *,
    python_args: Sequence[str] = (),
    duration_minutes: float = 22.0,
    timeout_minutes: float = 30.0,
    max_steps: int = 2000,
    quiet: bool = False,
) -> Tuple[str, ...]:
    """构造 ``scripts/run_game_flow.py`` 的 subprocess 参数。"""
    if duration_minutes <= 0:
        raise ValueError("duration_minutes 必须 > 0")
    if timeout_minutes <= 0:
        raise ValueError("timeout_minutes 必须 > 0")
    if max_steps < 1:
        raise ValueError("max_steps 必须 >= 1")
    if not str(config_path).strip():
        raise ValueError("config_path 不能为空")

    script = Path(repo_root) / "scripts" / "run_game_flow.py"
    command = [
        str(python_executable),
        *[str(part) for part in python_args],
        str(script),
        "--config",
        str(config_path),
        "--duration-minutes",
        f"{duration_minutes:g}",
        "--timeout-minutes",
        f"{timeout_minutes:g}",
        "--max-steps",
        str(int(max_steps)),
    ]
    if quiet:
        command.append("--quiet")
    return tuple(command)


def build_emulator_launch_command(
    emulator_path: Path,
    *,
    vm_index: int = 0,
) -> Tuple[str, ...]:
    """按可执行文件名判断 MuMuManager / MuMuPlayer 的启动参数。"""
    if vm_index < 0:
        raise ValueError("vm_index 必须 >= 0")
    path = Path(emulator_path)
    name = path.name.lower()
    if "mumumanager" in name:
        return (
            str(path),
            "control",
            "--vmindex",
            str(int(vm_index)),
            "launch",
        )
    return (str(path),)


def build_adb_connect_command(adb_path: str, address: str) -> Tuple[str, ...]:
    if not adb_path.strip():
        raise ValueError("adb_path 不能为空")
    if not address.strip():
        raise ValueError("address 不能为空")
    return (str(adb_path), "connect", address)


def build_adb_devices_command(adb_path: str) -> Tuple[str, ...]:
    if not adb_path.strip():
        raise ValueError("adb_path 不能为空")
    return (str(adb_path), "devices")


def command_preview(command: Sequence[str], *, max_length: int = 240) -> str:
    """把命令拼成便于日志显示的字符串。"""
    text = " ".join(f'"{part}"' if " " in part else part for part in command)
    return text if len(text) <= max_length else text[: max_length - 3] + "..."


def default_duration_minutes(value: Optional[float]) -> float:
    return 22.0 if value is None else float(value)
