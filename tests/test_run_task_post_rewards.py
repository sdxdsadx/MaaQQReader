from __future__ import annotations

import sys
from argparse import Namespace
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import run_task  # noqa: E402
from scripts import daily_all  # noqa: E402


def _args(task: str) -> Namespace:
    return Namespace(
        task=task,
        config="configs/qqreader.local.json",
        minutes=1.0,
        duration_minutes=None,
    )


def test_audiobook_gui_entry_runs_reward_cleanup_after_success(monkeypatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(run_task, "_run_legacy_task", lambda *_args: 0)
    monkeypatch.setattr(
        daily_all,
        "claim_audiobook_reward",
        lambda path: calls.append(str(path)) or True,
    )

    code = run_task._main(_args("DailyAudiobookFlow"), object(), object())

    assert code == 0
    assert calls == ["configs/qqreader.local.json"]


def test_reading_gui_entry_claims_reward_after_success(monkeypatch, tmp_path: Path) -> None:
    class FakeClient:
        def __init__(self) -> None:
            self.connected = False
            self.closed = False

        def connect(self) -> None:
            self.connected = True

        def close(self) -> None:
            self.closed = True

    client = FakeClient()
    monkeypatch.setattr(run_task, "_run_legacy_task", lambda *_args: 0)
    monkeypatch.setattr(run_task, "build_maa_client", lambda _config: client)
    # 阅读已改走 _run_reading_task（auto_read_30min.py 子进程）；不打桩会连真实设备。
    monkeypatch.setattr(run_task, "_run_reading_task", lambda *_args: 0)
    monkeypatch.setattr(
        run_task,
        "claim_reading_rewards",
        lambda *_args, **_kwargs: SimpleNamespace(succeeded=True, reason="已领取"),
    )
    config = SimpleNamespace(machine=SimpleNamespace(screenshot_dir=tmp_path))

    code = run_task._main(_args("DailyReadingFlow"), object(), config)

    assert code == 0
    assert client.connected is True
    assert client.closed is True
