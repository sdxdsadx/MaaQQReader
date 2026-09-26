"""GUI 长期开启后，启动任务前应使用磁盘上最新的任务参数。"""

from qqreader.gui.app import QQReaderGui
from qqreader.gui.commands import build_run_task_command
from qqreader.gui.task_catalog import DEFAULT_TASK_CATALOG, default_settings, save_task_settings


def test_starting_task_reloads_saved_timeout(tmp_path) -> None:
    gui = QQReaderGui.__new__(QQReaderGui)
    gui.repo_root = tmp_path
    gui._catalog = DEFAULT_TASK_CATALOG
    gui._settings = default_settings()
    gui._settings["DailyAdFlow"].values["timeout_minutes"] = 2
    gui._busy = False
    gui._require_config = lambda: object()
    gui._build_task_cards = lambda: None
    gui._cards_container = None

    saved = default_settings()
    saved["DailyAdFlow"].values["timeout_minutes"] = 45
    save_task_settings(tmp_path / "runtime" / "gui_tasks.json", saved)

    assert gui._prepare_serial() is True
    ad = next(spec for spec in DEFAULT_TASK_CATALOG if spec.key == "DailyAdFlow")
    command = build_run_task_command(
        "python", tmp_path, tmp_path / "config.json", ad.key,
        settings=gui._settings[ad.key].normalized(ad).values,
    )
    assert command[command.index("--timeout-minutes") + 1] == "45"
