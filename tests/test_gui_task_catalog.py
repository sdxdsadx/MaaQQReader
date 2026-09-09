"""任务目录、分级设置与串行计划测试。"""

from __future__ import annotations

from pathlib import Path

import pytest

from qqreader.gui.task_catalog import (
    DEFAULT_TASK_CATALOG,
    TaskSettings,
    build_serial_plan,
    default_settings,
    describe_catalog,
    load_task_order,
    load_task_settings,
    save_task_settings,
)


def test_catalog_migrates_old_gui_task_order() -> None:
    assert [spec.key for spec in DEFAULT_TASK_CATALOG] == [
        "LaunchQQReader",
        "SmokeTest",
        "DailyReadingFlow",
        "DailyAudiobookFlow",
        "DailyGameFlow",
        "DailyAdFlow",
        "DailyExternalAppFlow",
        "DailyLevelAdFlow",
        "ClaimOneReward",
    ]
    assert DEFAULT_TASK_CATALOG[2].legacy_name.startswith("01 每日自动阅读")
    assert DEFAULT_TASK_CATALOG[4].legacy_name.startswith("03 每日游戏")
    assert "（未接入）" in DEFAULT_TASK_CATALOG[2].display_name
    assert "（未接入）" not in DEFAULT_TASK_CATALOG[4].display_name


def test_default_settings_follow_old_defaults() -> None:
    settings = default_settings()
    assert settings["LaunchQQReader"].enabled is False
    assert settings["SmokeTest"].enabled is False
    assert settings["DailyGameFlow"].enabled is True
    assert settings["DailyAdFlow"].enabled is True
    assert settings["DailyReadingFlow"].enabled is False
    assert settings["DailyReadingFlow"].values["count"] == 2
    assert settings["DailyReadingFlow"].values["minutes"] == 35
    assert settings["DailyGameFlow"].values["count"] == 1
    assert settings["DailyGameFlow"].values["duration_minutes"] == 22.0


def test_serial_plan_expands_count_and_keeps_order() -> None:
    settings = default_settings()
    settings["DailyAdFlow"].enabled = False
    settings["DailyReadingFlow"].enabled = True
    settings["DailyReadingFlow"].values["count"] = 2
    settings["DailyGameFlow"].enabled = True
    settings["DailyGameFlow"].values["count"] = 1

    plan = build_serial_plan(settings)

    assert [item.spec.key for item in plan] == [
        "DailyReadingFlow",
        "DailyReadingFlow",
        "DailyGameFlow",
    ]
    assert plan[0].repeat_index == 1
    assert plan[1].repeat_index == 2
    assert plan[1].repeat_total == 2


def test_serial_plan_respects_saved_order() -> None:
    settings = default_settings()
    settings["DailyGameFlow"].enabled = True
    settings["DailyAdFlow"].enabled = True
    plan = build_serial_plan(
        settings, order=["DailyAdFlow", "DailyGameFlow"]
    )
    assert [item.spec.key for item in plan] == ["DailyAdFlow", "DailyGameFlow"]


def test_settings_and_order_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "gui_tasks.json"
    settings = default_settings()
    settings["DailyGameFlow"].enabled = False
    settings["DailyGameFlow"].values["duration_minutes"] = 0.5
    settings["DailyReadingFlow"].enabled = True
    settings["DailyReadingFlow"].values["minutes"] = 12.0

    save_task_settings(
        path,
        settings,
        order=["DailyAdFlow", "DailyGameFlow", "DailyReadingFlow"],
    )
    loaded = load_task_settings(path)
    order = load_task_order(path)

    assert loaded["DailyGameFlow"].enabled is False
    assert loaded["DailyGameFlow"].values["duration_minutes"] == 0.5
    assert loaded["DailyReadingFlow"].enabled is True
    assert loaded["DailyReadingFlow"].values["minutes"] == 12.0
    assert [spec.key for spec in order[:3]] == [
        "DailyAdFlow",
        "DailyGameFlow",
        "DailyReadingFlow",
    ]


def test_invalid_setting_is_rejected() -> None:
    spec = DEFAULT_TASK_CATALOG[4]  # DailyGameFlow
    field = spec.field("duration_minutes")
    with pytest.raises(ValueError):
        field.normalize(0)
    with pytest.raises(ValueError):
        field.normalize(9999)


def test_load_missing_file_returns_defaults(tmp_path: Path) -> None:
    loaded = load_task_settings(tmp_path / "missing.json")
    assert loaded["DailyGameFlow"].enabled is True
    assert loaded["DailyAdFlow"].enabled is True
    assert loaded["DailyReadingFlow"].enabled is False


def test_describe_catalog_mentions_old_tasks() -> None:
    text = describe_catalog()
    assert "每日自动阅读" in text
    assert "页面识别检查" in text
