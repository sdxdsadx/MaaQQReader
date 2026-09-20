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
        assert _button(root, "一键启动环境") is not None
        assert _button(root, "运行已勾选任务") is not None
        assert _button(root, "只运行当前卡片") is not None
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
