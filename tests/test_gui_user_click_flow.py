from __future__ import annotations

import tkinter as tk
from pathlib import Path

import pytest

from qqreader.gui.app import QQReaderGui


def _widgets(root: tk.Misc):
    for child in root.winfo_children():
        yield child
        yield from _widgets(child)


def _button(root: tk.Misc, text: str):
    return next(
        widget
        for widget in _widgets(root)
        if widget.winfo_class() in {"TButton", "Button"}
        and str(widget.cget("text")) == text
    )


def test_user_can_select_daily_flow_and_clear_it_with_one_click(tmp_path: Path) -> None:
    try:
        root = tk.Tk()
    except tk.TclError as exc:  # pragma: no cover - headless CI fallback
        pytest.skip(str(exc))
    root.withdraw()
    try:
        gui = QQReaderGui(root, repo_root=tmp_path)

        _button(root, "选择今日流程").invoke()
        enabled = {key for key, value in gui._settings.items() if value.enabled}
        assert enabled == {
            "DailyReadingFlow",
            "DailyAudiobookFlow",
            "DailyGameFlow",
            "DailyAdFlow",
            "DailyLevelAdFlow",
        }
        assert gui._settings["DailyGameFlow"].values["duration_minutes"] == 25

        _button(root, "全不选").invoke()
        assert not any(value.enabled for value in gui._settings.values())
        assert _button(root, "一键执行今日任务") is not None
        assert _button(root, "直接运行已选") is not None
        assert _button(root, "仅启动环境") is not None
        assert "尚未选择任务" in gui._selection_detail_var.get()
    finally:
        root.destroy()


def test_user_can_select_one_minute_trial_with_one_click(tmp_path: Path) -> None:
    try:
        root = tk.Tk()
    except tk.TclError as exc:  # pragma: no cover - headless CI fallback
        pytest.skip(str(exc))
    root.withdraw()
    try:
        gui = QQReaderGui(root, repo_root=tmp_path)

        _button(root, "选择1分钟试跑").invoke()

        enabled = {key for key, value in gui._settings.items() if value.enabled}
        assert enabled == {
            "DailyReadingFlow",
            "DailyAudiobookFlow",
            "DailyGameFlow",
        }
        assert gui._settings["DailyReadingFlow"].values["minutes"] == 1
        assert gui._settings["DailyAudiobookFlow"].values["minutes"] == 1
        assert gui._settings["DailyGameFlow"].values["duration_minutes"] == 1
    finally:
        root.destroy()


def test_one_click_daily_action_restores_formal_preset_and_starts_environment(
    tmp_path: Path,
) -> None:
    try:
        root = tk.Tk()
    except tk.TclError as exc:  # pragma: no cover - headless CI fallback
        pytest.skip(str(exc))
    root.withdraw()
    try:
        gui = QQReaderGui(root, repo_root=tmp_path)
        gui._clear_task_selection()
        calls: list[bool] = []
        gui._launch_environment = lambda run_daily=False: calls.append(run_daily)

        _button(root, "一键执行今日任务").invoke()

        assert calls == [True]
        assert gui._settings["DailyReadingFlow"].enabled is True
        assert gui._settings["DailyAudiobookFlow"].enabled is True
        assert gui._settings["DailyGameFlow"].values["duration_minutes"] == 25
    finally:
        root.destroy()


def test_settings_panel_is_hidden_until_user_requests_it(tmp_path: Path) -> None:
    try:
        root = tk.Tk()
    except tk.TclError as exc:  # pragma: no cover - headless CI fallback
        pytest.skip(str(exc))
    root.withdraw()
    try:
        gui = QQReaderGui(root, repo_root=tmp_path)
        assert gui._settings_panel.winfo_manager() == ""

        _button(root, "设置").invoke()
        assert gui._settings_panel.winfo_manager() == "pack"

        _button(root, "设置").invoke()
        assert gui._settings_panel.winfo_manager() == ""
    finally:
        root.destroy()


def test_weekly_reading_button_selects_only_ten_reading_runs(tmp_path: Path) -> None:
    try:
        root = tk.Tk()
    except tk.TclError as exc:  # pragma: no cover - headless CI fallback
        pytest.skip(str(exc))
    root.withdraw()
    try:
        gui = QQReaderGui(root, repo_root=tmp_path)

        _button(root, "每周阅读600分钟").invoke()

        enabled = {key for key, value in gui._settings.items() if value.enabled}
        assert enabled == {"DailyReadingFlow"}
        assert gui._settings["DailyReadingFlow"].values["count"] == 10
        assert gui._settings["DailyReadingFlow"].values["minutes"] == 35
        assert "实际执行 10 步" in gui._selection_summary_var.get()
        assert "计时约 350 分钟" in gui._selection_summary_var.get()
    finally:
        root.destroy()
