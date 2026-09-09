"""GUI 纯逻辑测试：命令构造、模拟器识别、参数校验。"""

from __future__ import annotations

from pathlib import Path

import pytest

from qqreader.gui.commands import (
    build_adb_connect_command,
    build_adb_devices_command,
    build_emulator_launch_command,
    build_run_game_flow_command,
    command_preview,
)


def test_build_run_game_flow_command(tmp_path: Path) -> None:
    config = tmp_path / "qqreader.local.json"
    command = build_run_game_flow_command(
        "python.exe",
        tmp_path,
        config,
        duration_minutes=0.02,
        timeout_minutes=3,
        max_steps=400,
    )
    assert command[0] == "python.exe"
    assert command[1].endswith(str(Path("scripts") / "run_game_flow.py"))
    assert "--config" in command
    assert str(config) in command
    assert command[command.index("--duration-minutes") + 1] == "0.02"
    assert command[command.index("--timeout-minutes") + 1] == "3"
    assert command[command.index("--max-steps") + 1] == "400"


def test_run_command_rejects_invalid_parameters(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        build_run_game_flow_command(
            "python.exe", tmp_path, tmp_path / "c.json", duration_minutes=0
        )
    with pytest.raises(ValueError):
        build_run_game_flow_command(
            "python.exe", tmp_path, tmp_path / "c.json", timeout_minutes=0
        )
    with pytest.raises(ValueError):
        build_run_game_flow_command(
            "python.exe", tmp_path, tmp_path / "c.json", max_steps=0
        )


def test_emulator_launch_command_for_mumu_manager() -> None:
    path = Path("D:/MuMu/MuMuManager.exe")
    command = build_emulator_launch_command(path, vm_index=1)
    assert command == (
        str(path),
        "control",
        "--vmindex",
        "1",
        "launch",
    )


def test_emulator_launch_command_for_player() -> None:
    path = Path("D:/MuMu/MuMuPlayer.exe")
    command = build_emulator_launch_command(path)
    assert command == (str(path),)


def test_adb_commands() -> None:
    assert build_adb_connect_command("adb.exe", "127.0.0.1:16384") == (
        "adb.exe",
        "connect",
        "127.0.0.1:16384",
    )
    assert build_adb_devices_command("adb.exe") == ("adb.exe", "devices")


def test_command_preview_quotes_spaces() -> None:
    preview = command_preview(("python.exe", "C:/a b/run.py", "--x", "1"))
    assert '"C:/a b/run.py"' in preview
    assert preview.startswith("python.exe")
