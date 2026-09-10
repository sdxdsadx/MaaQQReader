"""QQR-35：主循环基础轮询间隔（页面识别节流）。

锁定行为：
* 无动作轮次（NOOP / REOBSERVE）每轮等待 poll_seconds（默认 10s）；
* 实际触控动作（点击 / 返回 / 滑动）后只等 action_feedback_seconds；
* WAIT 动作自带等待时长，不额外叠加节流；
* poll_seconds=0 时恢复原有零间隔语义（时间敏感测试的逃生门）。
"""

from __future__ import annotations

from qqreader.contract.conditions import Always, Never
from qqreader.contract.outcome import TaskOutcome
from qqreader.runtime.context import StepResult
from qqreader.runner.runner import RunnerConfig, TaskRunner
from tests.helpers import (
    FakeAdapter,
    FakeClock,
    QueueObserver,
    home_observation,
    make_contract,
    make_definition,
)


def _poll_loop_contract(timeout_seconds: float = 60.0):
    return make_contract(
        name="qqr35",
        start_condition=Always(),
        ready_condition=Always(),
        progress_condition=Never(),
        success_condition=Never(),
        timeout_seconds=timeout_seconds,
    )


def test_idle_loops_throttle_to_poll_seconds() -> None:
    """无动作轮次每轮叠加 poll_seconds，直到独立超时。"""
    observer = QueueObserver([home_observation()])
    adapter = FakeAdapter()
    definition = make_definition(_poll_loop_contract(timeout_seconds=60.0), observer, adapter)

    result = TaskRunner(
        definition,
        FakeClock(),
        config=RunnerConfig(poll_seconds=10.0, recovery_pause_seconds=0.0),
    ).run()

    assert result.outcome is TaskOutcome.TIMEOUT
    assert result.ended_at is not None
    # 轮询间隔主导空调节奏：每轮空转 +10s，60s 内轮次远少于旧版零间隔。
    assert adapter.advances, "空转轮次应持续调用适配器推进"
    assert len(adapter.advances) <= 8  # 60s / 10s + 少量首循环


def test_action_then_short_feedback_gap() -> None:
    """触控动作后的下一轮只等 action_feedback_seconds（而不是 10s）。"""
    tap_step = StepResult("点击坐标", actions=("TAP_POINT",), progress=True)
    definition = make_definition(
        _poll_loop_contract(timeout_seconds=6.0),
        QueueObserver([home_observation()]),
        FakeAdapter(steps=[tap_step] * 20),
    )

    result = TaskRunner(
        definition,
        FakeClock(),
        config=RunnerConfig(poll_seconds=10.0, action_feedback_seconds=2.0),
    ).run()

    assert result.outcome is TaskOutcome.TIMEOUT
    assert result.ended_at is not None
    assert result.ended_at - result.started_at <= 7.0


def test_wait_action_not_double_throttled() -> None:
    """WAIT 自带时长：节流不应在 WAIT 之上再叠加 10s。"""
    wait_step = StepResult("等待 3s", actions=("WAIT",), progress=True)
    definition = make_definition(
        _poll_loop_contract(timeout_seconds=8.0),
        QueueObserver([home_observation()]),
        FakeAdapter(
            steps=[wait_step] * 20,
            on_advance=lambda ctx: ctx.clock.sleep(3.0, ctx.token),
        ),
    )

    result = TaskRunner(
        definition,
        FakeClock(),
        config=RunnerConfig(poll_seconds=10.0),
    ).run()

    assert result.outcome is TaskOutcome.TIMEOUT
    # 若 WAIT 被额外叠加 10s，单轮 >13s，8s 内最多 1 轮；正常 3s/轮。
    assert result.ended_at is not None
    assert result.ended_at - result.started_at <= 9.0
