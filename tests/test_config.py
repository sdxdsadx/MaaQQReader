"""QQR-2：配置模型（机器差异外置、UTF-8、中文/空格路径、清晰报错）。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from qqreader.config import (
    ConfigError,
    default_config,
    load_config,
    loads_config,
)
from qqreader.config.__main__ import main
from qqreader.config.model import CaptchaConfig


def _valid_data() -> dict:
    return {
        "version": 1,
        "machine": {
            "adb_path": "C:\\tools\\adb.exe",
            "adb_address": "127.0.0.1:16384",
            "package_name": "com.qq.reader",
            "resolution": [720, 1280],
            "screenshot_dir": "runtime/screenshots",
            "log_dir": "runtime/logs",
            "record_dir": "runtime/records",
        },
        "captcha": {
            "solver": "manual",
            "max_attempts": 2,
            "verify_frames": 3,
            "verify_interval_seconds": 1.0,
        },
        "tasks": {
            "DailyAdFlow": {"enabled": True, "timeout_seconds": 2700, "retry": 3},
            "DailyGameFlow": {"enabled": False, "timeout_seconds": 1800, "retry": 3},
        },
    }


def _write_json(base: Path, data: dict, name: str = "qqreader.json") -> Path:
    path = base / name
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def test_load_json_config(tmp_path: Path) -> None:
    path = _write_json(tmp_path, _valid_data())
    config = load_config(path)
    assert config.version == 1
    assert config.machine.adb_address == "127.0.0.1:16384"
    assert config.machine.resolution == (720, 1280)
    assert config.task("DailyAdFlow").timeout_seconds == 2700
    assert config.source == path.resolve()


def test_relative_dirs_resolve_against_config_dir(tmp_path: Path) -> None:
    config = load_config(_write_json(tmp_path, _valid_data()))
    assert config.machine.screenshot_dir == tmp_path / "runtime/screenshots"
    assert config.machine.log_dir == tmp_path / "runtime" / "logs"
    assert config.machine.record_dir == tmp_path / "runtime" / "records"


def test_chinese_and_space_path(tmp_path: Path) -> None:
    base = tmp_path / "中文 目录"
    base.mkdir()
    config = load_config(_write_json(base, _valid_data()))
    assert config.machine.screenshot_dir == base / "runtime" / "screenshots"
    assert "中文 目录" in str(config.machine.screenshot_dir)


def test_missing_required_field_is_clear(tmp_path: Path) -> None:
    data = _valid_data()
    del data["machine"]["adb_path"]
    with pytest.raises(ConfigError) as exc:
        load_config(_write_json(tmp_path, data))
    message = str(exc.value)
    assert "machine.adb_path" in message
    assert "qqreader.example" in message


def test_missing_machine_section_is_clear(tmp_path: Path) -> None:
    data = _valid_data()
    del data["machine"]
    with pytest.raises(ConfigError, match="machine"):
        load_config(_write_json(tmp_path, data))


def test_env_override_machine(tmp_path: Path) -> None:
    path = _write_json(tmp_path, _valid_data())
    config = load_config(
        path,
        env={
            "QQREADER_ADB_ADDRESS": "127.0.0.1:7555",
            "QQREADER_RESOLUTION": "1080x1920",
        },
    )
    assert config.machine.adb_address == "127.0.0.1:7555"
    assert config.machine.resolution == (1080, 1920)


def test_env_override_invalid_int_is_clear(tmp_path: Path) -> None:
    path = _write_json(tmp_path, _valid_data())
    with pytest.raises(ConfigError, match="QQREADER_CAPTCHA_MAX_ATTEMPTS"):
        load_config(path, env={"QQREADER_CAPTCHA_MAX_ATTEMPTS": "abc"})


def test_unknown_top_level_key_rejected(tmp_path: Path) -> None:
    data = _valid_data()
    data["machien"] = {}  # 常见拼写错误
    with pytest.raises(ConfigError, match="未知字段"):
        load_config(_write_json(tmp_path, data))


def test_unsupported_suffix_rejected(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    path.write_text("", encoding="utf-8")
    with pytest.raises(ConfigError, match="不支持的配置格式"):
        load_config(path)


def test_yaml_config(tmp_path: Path) -> None:
    yaml = pytest.importorskip("yaml")
    path = tmp_path / "qqreader.yaml"
    path.write_text(
        yaml.safe_dump(_valid_data(), allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    config = load_config(path)
    assert config.machine.adb_address == "127.0.0.1:16384"
    assert config.task("DailyGameFlow").enabled is False


def test_loads_config_from_memory() -> None:
    config = loads_config(
        json.dumps(_valid_data(), ensure_ascii=False),
        base_dir=Path("D:/项目/QQReader"),
    )
    assert config.machine.screenshot_dir == Path(
        "D:/项目/QQReader/runtime/screenshots"
    )


def test_default_config_is_placeholder_only() -> None:
    config = default_config()
    assert config.machine.adb_address == "127.0.0.1:16384"
    assert "path" in config.machine.adb_path.lower()
    assert config.task("DailyAdFlow").timeout_seconds == 2700


def test_task_lookup_error_is_clear() -> None:
    with pytest.raises(ConfigError, match="没有任务"):
        default_config().task("NoSuchTask")


def test_captcha_defaults_to_manual() -> None:
    captcha = CaptchaConfig()
    assert captcha.solver == "manual"
    assert captcha.verify_frames >= 1


def test_cli_check_ok(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    path = _write_json(tmp_path, _valid_data())
    assert main(["check", "--config", str(path)]) == 0
    assert "配置读取成功" in capsys.readouterr().out


def test_cli_show_prints_summary(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    path = _write_json(tmp_path, _valid_data())
    assert main(["show", "--config", str(path)]) == 0
    out = capsys.readouterr().out
    assert "机器配置" in out
    assert "DailyAdFlow" in out


def test_cli_missing_required_returns_2(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    data = _valid_data()
    del data["machine"]["adb_address"]
    path = _write_json(tmp_path, data)
    assert main(["check", "--config", str(path)]) == 2
    assert "machine.adb_address" in capsys.readouterr().err
