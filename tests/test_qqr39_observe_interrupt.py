"""QQR-39：观测/确认期间跨过独立超时或收到取消，执行器不得判成功，也不得再执行领域动作。

复现场景来自 Issue：
1. Observer 第 3 次 ``observe()`` 内把时钟推进 2s（超时 1s），然后返回 HOME；
   旧实现返回 SUCCESS 并写 ``task.success``。
2. Observer 第 3 次 ``observe()`` 内调用 ``token.cancel()``；
   旧实现返回 CANCELLED，但取消后仍执行了一次 ``step.advance``。
"""

from __future__ import annotations

from qqreader.contract.conditions import Always, Never, state_in
from qqreader.contract.outcome import TaskOutcome
from qqreader.page.states import PageState, RunState
from qqreader.runner.runner import TaskRunner
from qqreader.runtime.clock import CancellationToken, FakeClock
from tests.helpers import FakeAdapter, QueueObserver, home_observation, make_contract, make_definition


class _HookObserver(QueueObserver):
    """第 ``trigger_call`` 次观测时执行 ``hook(context)``，模拟耗时截图/OCR 或观测中途停止。"""

    def __init__(self, trigger_call, hook) -> None:
        super().__init__([home_observation()])
        self._trigger_call = trigger_call
        self._hook = hook

    def observe(self, context, *, deep: bool = False):
        observation = super().observe(context, deep=deep)
        if self.calls == self._trigger_call:
            self._hook(context)
        return observation


def _contract(success_condition, timeout_seconds: float):
    return make_contract(
        name="qqr39",
        start_condition=Always(),
        ready_condition=Always(),
        progress_condition=Always(),
        success_condition=success_condition,
        timeout_seconds=timeout_seconds,
    )


def _events(result):
    return [event.kind for event in result.diagnostics]


def test_observe_crossing_timeout_does_not_report_success() -> None:
    clock = FakeClock()
    observer = _HookObserver(3, lambda ctx: clock.advance(2.0))
    adapter = FakeAdapter()
    definition = make_definition(_contract(state_in(PageState.HOME), 1.0), observer, adapter)

    result = TaskRunner(definition, clock).run()

    assert result.outcome is TaskOutcome.TIMEOUT
    assert result.run_state is RunState.TIMEOUT
    assert "task.success" not in _events(result)
    assert adapter.advances == []
    assert observer.calls == 3


def test_cancel_during_observe_stops_before_any_domain_action() -> None:
    token = CancellationToken()
    observer = _HookObserver(3, lambda ctx: token.cancel("test stop"))
    adapter = FakeAdapter()
    definition = make_definition(_contract(Never(), 60.0), observer, adapter)

    result = TaskRunner(definition, FakeClock(), token=token).run()

    assert result.outcome is TaskOutcome.CANCELLED
    assert "test stop" in result.reason
    assert adapter.advances == []
    assert "step.advance" not in _events(result)


def test_cancel_during_observe_before_success_is_not_success() -> None:
    token = CancellationToken()
    observer = _HookObserver(3, lambda ctx: token.cancel("user stop"))
    adapter = FakeAdapter()
    definition = make_definition(_contract(state_in(PageState.HOME), 60.0), observer, adapter)

    result = TaskRunner(definition, FakeClock(), token=token).run()

    assert result.outcome is TaskOutcome.CANCELLED
    assert "task.success" not in _events(result)


def test_normal_success_within_timeout_still_succeeds() -> None:
    clock = FakeClock()
    observer = _HookObserver(3, lambda ctx: clock.advance(0.2))
    definition = make_definition(_contract(state_in(PageState.HOME), 1.0), observer, FakeAdapter())

    result = TaskRunner(definition, clock).run()

    assert result.outcome is TaskOutcome.SUCCESS
