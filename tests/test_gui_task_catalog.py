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
    load_task_settings,
    save_task_settings,
)


def test_default_catalog_is_grouped_and_ordered() -> None:
    assert [spec.key for spec in DEFAULT_TASK_CATALOG] == [
        "DailyGameFlow",
        "DailyAdFlow",
    ]
    assert DEFAULT_TASK_CATALOG[0].group == "日常任务"
    assert DEFAULT_TASK_CATALOG[0].default_enabled is True
    assert DEFAULT_TASK_CATALOG[1].default_enabled is False
    assert "DailyGameFlow" in describe_catalog()


def test_serial_plan_only_enabled_tasks_in_catalog_order() -> None:
    settings = default_settings()
    settings["DailyAdFlow"].enabled = True
    settings["DailyGameFlow"].enabled = True

    plan = build_serial_plan(settings)

    assert [item.spec.key for item in plan] == ["DailyGameFlow", "DailyAdFlow"]
    assert plan[0].settings.value(plan[0].spec, "duration_minutes") == 22.0


def test_serial_plan_skips_disabled_tasks() -> None:
    settings = default_settings()
    settings["DailyGameFlow"].enabled = False
    assert build_serial_plan(settings) == []


def test_settings_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "gui_tasks.json"
    settings = default_settings()
    settings["DailyGameFlow"].enabled = False
    settings["DailyGameFlow"].values["duration_minutes"] = 0.5
    settings["DailyAdFlow"].enabled = True
    settings["DailyAdFlow"].values["timeout_minutes"] = 12.0

    save_task_settings(path, settings)
    loaded = load_task_settings(path)

    assert loaded["DailyGameFlow"].enabled is False
    assert loaded["DailyGameFlow"].values["duration_minutes"] == 0.5
    assert loaded["DailyAdFlow"].enabled is True
    assert loaded["DailyAdFlow"].values["timeout_minutes"] == 12.0


def test_invalid_setting_is_rejected() -> None:
    spec = DEFAULT_TASK_CATALOG[0]
    field = spec.field("duration_minutes")
    with pytest.raises(ValueError):
        field.normalize(0)
    with pytest.raises(ValueError):
        field.normalize(9999)


def test_load_missing_file_returns_defaults(tmp_path: Path) -> None:
    loaded = load_task_settings(tmp_path / "missing.json")
    assert loaded["DailyGameFlow"].enabled is True
    assert loaded["DailyAdFlow"].enabled is False
