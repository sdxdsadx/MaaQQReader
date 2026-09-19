from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from qqreader.workflow import (
    DailyFlowRecorder,
    DailyFlowRun,
    FlowRunState,
    FlowStepSnapshot,
    FlowStepState,
    business_day,
)


def at(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 9, 19, hour, minute, tzinfo=timezone.utc)


def snapshots() -> tuple[FlowStepSnapshot, ...]:
    return (
        FlowStepSnapshot.create(
            step_id="01-read-1",
            task_key="DailyReadingFlow",
            display_name="自动阅读",
            settings={"minutes": 35, "count": 2},
            repeat_index=1,
            repeat_total=2,
        ),
        FlowStepSnapshot.create(
            step_id="02-game-1",
            task_key="DailyGameFlow",
            display_name="游戏",
            settings={"duration_minutes": 25},
        ),
    )


def test_business_day_changes_at_four_in_china() -> None:
    assert business_day(datetime.fromisoformat("2026-09-19T03:59:00+08:00")).isoformat() == "2026-09-18"
    assert business_day(datetime.fromisoformat("2026-09-19T04:00:00+08:00")).isoformat() == "2026-09-19"


def test_failed_step_can_continue_and_finishes_with_errors() -> None:
    run = DailyFlowRun.start(snapshots(), at=at(0), run_id="run")
    assert run.current is run.steps[0]

    run.complete_current(2, reason="奖励证据不足", at=at(0, 1))
    run.start_next(at(0, 2))
    run.complete_current(0, at=at(0, 3))

    assert run.state is FlowRunState.COMPLETED_WITH_ERRORS
    assert [step.state for step in run.steps] == [
        FlowStepState.FAILED,
        FlowStepState.SUCCEEDED,
    ]
    assert run.steps[0].reason == "奖励证据不足"


def test_user_stop_cancels_current_and_skips_future_steps() -> None:
    run = DailyFlowRun.start(snapshots(), at=at(0), run_id="run")

    run.stop_by_user(at=at(0, 1))

    assert run.state is FlowRunState.CANCELLED
    assert [step.state for step in run.steps] == [
        FlowStepState.CANCELLED,
        FlowStepState.SKIPPED,
    ]


def test_all_successful_steps_finish_successfully() -> None:
    run = DailyFlowRun.start(snapshots(), at=at(0), run_id="run")
    run.complete_current(0, at=at(0, 1))
    run.start_next(at(0, 2))
    run.complete_current(0, at=at(0, 3))
    assert run.state is FlowRunState.SUCCEEDED


def test_configuration_is_frozen_and_record_is_atomic(tmp_path) -> None:
    mutable = {"minutes": 35}
    snapshot = FlowStepSnapshot.create(
        step_id="01-read",
        task_key="DailyReadingFlow",
        display_name="自动阅读",
        settings=mutable,
    )
    mutable["minutes"] = 1
    run = DailyFlowRun.start((snapshot,), at=at(0), run_id="known-run")
    recorder = DailyFlowRecorder(tmp_path)

    path = recorder.save(run)
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert payload["steps"][0]["settings"]["minutes"] == 35
    assert payload["state"] == "RUNNING"
    assert not path.with_suffix(".json.tmp").exists()


def test_invalid_or_duplicate_steps_are_rejected() -> None:
    with pytest.raises(ValueError):
        FlowStepSnapshot.create(step_id="", task_key="task", display_name="name")
    same = snapshots()[0]
    with pytest.raises(ValueError):
        DailyFlowRun.start((same, same), at=at(0))
