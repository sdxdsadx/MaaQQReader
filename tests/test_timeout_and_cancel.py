"""超时与取消语义。

验收要求：单元测试覆盖超时与取消。关键语义：

* 超时结果是 ``TIMEOUT``，取消结果是 ``CANCELLED``，二者都不是 ``FAILED``；
* 每个任务的超时相互独立；
* 取消可以在循环之间、适配器推进中、以及 sleep 期间生效。
"""

from __future__ import annotations

from qqreader.contract.conditions import Always, Never
from qqreader.contract.outcome import TaskOutcome
from qqreader.page.states import RunState
from qqreader.runner.runner import RunnerConfig, TaskRunner
from qqreader.runtime.clock import CancellationToken, FakeClock
from tests.helpers import (
    FakeAdapter,
    QueueObserver,
    home_observation,
    make_contract,
    make_definition,
)


def _never_success_contract(timeout_seconds: float):
    return make_contract(
        name=f"never_{timeout_seconds:g}",
        start_condition=Always(),
        ready_condition=Always(),
        progress_condition=Always(),
        success_condition=Never(),
        timeout_seconds=timeout_seconds,
    )


def _sleeping_adapter():
    return FakeAdapter(on_advance=lambda ctx: ctx.clock.sleep(1.0, ctx.token))


def test_timeout_returns_timeout_not_failed() -> None:
    observer = QueueObserver([home_observation()])
    definition = make_definition(_never_success_contract(3.0), observer, _sleeping_adapter())
    result = TaskRunner(definition, FakeClock()).run()
    assert result.outcome is TaskOutcome.TIMEOUT
    assert result.run_state is RunState.TIMEOUT
    assert "独立超时 3s" in result.reason
    assert result.outcome is not TaskOutcome.FAILED


def test_each_task_has_independent_timeout() -> None:
    observer_a = QueueObserver([home_observation()])
    observer_b = QueueObserver([home_observation()])
    short = TaskRunner(
        make_definition(_never_success_contract(2.0), observer_a, _sleeping_adapter()),
        FakeClock(),
    ).run()
    long = TaskRunner(
        make_definition(_never_success_contract(7.0), observer_b, _sleeping_adapter()),
        FakeClock(),
    ).run()
    assert short.outcome is TaskOutcome.TIMEOUT
    assert long.outcome is TaskOutcome.TIMEOUT
    assert "独立超时 2s" in short.reason
    assert "独立超时 7s" in long.reason


def test_cancel_before_run_returns_cancelled() -> None:
    token = CancellationToken()
    token.cancel("用户停止")
    observer = QueueObserver([home_observation()])
    result = TaskRunner(
        make_definition(_never_success_contract(60.0), observer, FakeAdapter()),
        FakeClock(),
        token=token,
    ).run()
    assert result.outcome is TaskOutcome.CANCELLED
    assert result.run_state is RunState.CANCELLED
    assert "用户停止" in result.reason


def test_cancel_during_advance_returns_cancelled() -> None:
    token = CancellationToken()
    adapter = FakeAdapter(on_advance=lambda ctx: ctx.token.cancel("用户停止"))
    observer = QueueObserver([home_observation()])
    result = TaskRunner(
        make_definition(_never_success_contract(60.0), observer, adapter),
        FakeClock(),
        token=token,
    ).run()
    assert result.outcome is TaskOutcome.CANCELLED
    assert result.outcome is not TaskOutcome.FAILED


def test_cancel_during_sleep_returns_cancelled() -> None:
    token = CancellationToken()
    clock = FakeClock(on_sleep=lambda index, seconds: token.cancel("用户停止"))
    adapter = FakeAdapter(on_advance=lambda ctx: ctx.clock.sleep(5.0, ctx.token))
    observer = QueueObserver([home_observation()])
    result = TaskRunner(
        make_definition(_never_success_contract(60.0), observer, adapter),
        clock,
        token=token,
    ).run()
    assert result.outcome is TaskOutcome.CANCELLED
    assert clock.sleeps == [5.0]
    assert result.outcome is not TaskOutcome.FAILED


def test_cancel_is_not_timeout_even_if_time_advanced() -> None:
    token = CancellationToken()

    def cancel_and_advance(ctx) -> None:
        ctx.clock.advance(999.0)
        ctx.token.cancel("用户停止")

    adapter = FakeAdapter(on_advance=cancel_and_advance)
    observer = QueueObserver([home_observation()])
    result = TaskRunner(
        make_definition(_never_success_contract(60.0), observer, adapter),
        FakeClock(),
        token=token,
        config=RunnerConfig(),
    ).run()
    # 取消优先级高于超时检查：结果是 CANCELLED，不是 TIMEOUT。
    assert result.outcome is TaskOutcome.CANCELLED
