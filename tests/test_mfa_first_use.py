"""MFAAvalonia 新手教程：启动前把「已完成」写进 ``mfa/config/config.json``。"""

from __future__ import annotations

import json
from pathlib import Path

from qqreader.mfa import first_use
from qqreader.mfa.first_use import TUTORIAL_KEY, ensure_tutorial_completed

REPO_ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = REPO_ROOT / "启动QQReaderGUI.cmd"

# 2026-10-12 主目录 mfa/config/config.json 在看完教程之前的真实内容（MFAAvalonia v2.16.2 写出）。
REAL_CONFIG_BEFORE_TUTORIAL = {
    "CurrentLanguage": "zh-CN",
    "ResourceUpdateChannelInitialized": True,
    "ColorTheme": "Blue",
    "BaseTheme": "Light",
    "EnableEdit": False,
    "UI.MainWindow.Maximized": "false",
    "UI.MainWindow.Width": "1920",
    "UI.MainWindow.Height": "1023",
    "UI.MainWindow.PositionX": "207",
    "UI.MainWindow.PositionY": "184",
    "EnableCheckVersion": False,
}


def _read(mfa_dir: Path) -> dict:
    return json.loads((mfa_dir / "config" / "config.json").read_text(encoding="utf-8"))


def test_fresh_copy_without_config_dir_gets_flag(tmp_path):
    # 全新解压 / 新 worktree：mfa/config 被 .gitignore 忽略，整个目录都不存在
    assert ensure_tutorial_completed(tmp_path) is True
    assert _read(tmp_path) == {TUTORIAL_KEY: True}


def test_existing_config_keeps_other_keys(tmp_path):
    config = tmp_path / "config" / "config.json"
    config.parent.mkdir()
    config.write_text(json.dumps(REAL_CONFIG_BEFORE_TUTORIAL, indent=2), encoding="utf-8")

    assert ensure_tutorial_completed(tmp_path) is True
    assert _read(tmp_path) == {**REAL_CONFIG_BEFORE_TUTORIAL, TUTORIAL_KEY: True}


def test_flag_false_is_turned_on(tmp_path):
    config = tmp_path / "config" / "config.json"
    config.parent.mkdir()
    config.write_text(json.dumps({TUTORIAL_KEY: False, "BaseTheme": "Dark"}), encoding="utf-8")

    assert ensure_tutorial_completed(tmp_path) is True
    assert _read(tmp_path) == {TUTORIAL_KEY: True, "BaseTheme": "Dark"}


def test_already_completed_is_not_rewritten(tmp_path):
    config = tmp_path / "config" / "config.json"
    config.parent.mkdir()
    original = json.dumps({**REAL_CONFIG_BEFORE_TUTORIAL, TUTORIAL_KEY: True}, indent=2)
    config.write_text(original, encoding="utf-8")

    assert ensure_tutorial_completed(tmp_path) is False
    assert config.read_text(encoding="utf-8") == original


def test_utf8_bom_config_is_read(tmp_path):
    config = tmp_path / "config" / "config.json"
    config.parent.mkdir()
    config.write_bytes(b"\xef\xbb\xbf" + json.dumps({"BaseTheme": "Dark"}).encode("utf-8"))

    assert ensure_tutorial_completed(tmp_path) is True
    assert _read(tmp_path) == {"BaseTheme": "Dark", TUTORIAL_KEY: True}
    assert not config.read_bytes().startswith(b"\xef\xbb\xbf")


def test_unreadable_config_is_left_alone(tmp_path):
    # 读不懂的配置不覆盖：宁可再弹一次教程，也不丢用户的界面设置
    config = tmp_path / "config" / "config.json"
    config.parent.mkdir()
    config.write_text("{ not json", encoding="utf-8")

    assert ensure_tutorial_completed(tmp_path) is False
    assert config.read_text(encoding="utf-8") == "{ not json"


def test_non_object_config_is_left_alone(tmp_path):
    config = tmp_path / "config" / "config.json"
    config.parent.mkdir()
    config.write_text("[]", encoding="utf-8")

    assert ensure_tutorial_completed(tmp_path) is False
    assert config.read_text(encoding="utf-8") == "[]"


def test_main_never_fails_the_launcher(tmp_path, capsys):
    assert first_use.main([str(tmp_path)]) == 0
    assert _read(tmp_path)[TUTORIAL_KEY] is True
    assert "新手教程" in capsys.readouterr().out

    (tmp_path / "config" / "config.json").write_text("{ not json", encoding="utf-8")
    assert first_use.main([str(tmp_path)]) == 0


def test_launcher_marks_tutorial_before_starting_mfa():
    text = LAUNCHER.read_text(encoding="utf-8")
    mark = text.index("-m qqreader.mfa.first_use")
    start = text.index('start "" /D "%ROOT%mfa" "%MFAEXE%"')
    assert mark < start
