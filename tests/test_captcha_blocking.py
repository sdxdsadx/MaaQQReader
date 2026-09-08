"""验证码状态阻塞与「求解后确认」语义（AGENTS.md §3.8）。

这些测试锁定 P0 行为：

* 检测到验证码后正常推进暂停，适配器不得点击；
* 求解器报告成功不算数，必须重新观测确认验证码消失；
* 无法处理时进入 ``WAITING_FOR_HUMAN``，结果是 ``BLOCKED_BY_CAPTCHA``，
  不是 ``FAILED``；
* 即使状态识别器判为 ``UNKNOWN``，只要验证码特征命中也要进入守卫。
"""

from __future__ import annotations

from qqreader.captcha.guard import (
    CaptchaOutcome,
    CaptchaResolution,
    ManualCaptchaGuard,
    SolveResult,
    VerifyingCaptchaGuard,
)
from qqreader.contract.conditions import Always, Never, feature
from qqreader.contract.outcome import TaskOutcome
from qqreader.page.feature_keys import DEFAULT_FEATURE_KEYS
from qqreader.page.features import FeatureKind, FeatureSpec
from qqreader.page.states import PageState, RunState
from qqreader.runner.runner import TaskRunner
from qqreader.runtime.clock import FakeClock
from tests.helpers import (
    FakeAdapter,
    FakeSolver,
    QueueObserver,
    StubCaptchaGuard,
    captcha_observation,
    home_observation,
    make_contract,
    make_context,
    make_definition,
    make_recognizer,
    reward_observation,
)
from qqreader.tasks.common import captcha_condition


def _captcha_contract(success=None):
    return make_contract(
        name="captcha_task",
        start_condition=Always(),
        ready_condition=Always(),
        progress_condition=Always(),
        captcha_condition=captcha_condition(DEFAULT_FEATURE_KEYS),
        success_condition=success or Never(),
        timeout_seconds=60.0,
    )


def test_captcha_blocks_and_never_taps_or_recovers() -> None:
    observer = QueueObserver([captcha_observation()])
    adapter = FakeAdapter()
    guard = StubCaptchaGuard(
        [CaptchaOutcome(CaptchaResolution.WAITING_FOR_HUMAN, 0, "需要人工")]
    )
    result = TaskRunner(
        make_definition(_captcha_contract(), observer, adapter, captcha_guard=guard),
        FakeClock(),
    ).run()

    assert result.outcome is TaskOutcome.BLOCKED_BY_CAPTCHA
    assert result.run_state is RunState.WAITING_FOR_HUMAN
    assert result.final_state is PageState.CAPTCHA
    assert adapter.advances == []
    assert adapter.recoveries == []
    assert guard.calls == 1


def test_captcha_state_triggers_guard_even_when_condition_false() -> None:
    contract = make_contract(
        name="captcha_state_only",
        captcha_condition=Never(),  # 条件故意写死为假
        success_condition=Never(),
        timeout_seconds=60.0,
    )
    observer = QueueObserver([captcha_observation()])
    guard = StubCaptchaGuard()
    adapter = FakeAdapter()
    result = TaskRunner(
        make_definition(contract, observer, adapter, captcha_guard=guard),
        FakeClock(),
    ).run()
    assert guard.calls == 1
    assert result.outcome is TaskOutcome.BLOCKED_BY_CAPTCHA
    assert adapter.advances == []


def test_solver_verified_gone_allows_task_to_continue() -> None:
    observer = QueueObserver(
        [captcha_observation(), reward_observation(ocr=("12/12",))]
    )
    solver = FakeSolver([SolveResult(True, "已提交")])
    contract = _captcha_contract(
        success=feature(FeatureSpec(kind=FeatureKind.OCR, key="12/12"))
    )
    guard = VerifyingCaptchaGuard(
        solver=solver,
        observer=observer,
        recognizer=make_recognizer(),
        captcha_condition=contract.captcha_condition,
    )
    adapter = FakeAdapter()
    result = TaskRunner(
        make_definition(contract, observer, adapter, captcha_guard=guard),
        FakeClock(),
    ).run()

    assert result.outcome is TaskOutcome.SUCCESS
    assert solver.calls == 1
    kinds = [event.kind for event in result.diagnostics]
    assert "captcha.verified_gone" in kinds
    # 验证码消失后重新进入正常流程，最终由 success_condition 结束。
    assert "task.success" in kinds


def test_solver_claims_solved_but_captcha_persists_blocks() -> None:
    observer = QueueObserver([captcha_observation()])
    solver = FakeSolver([SolveResult(True, "第一次提交"), SolveResult(True, "第二次提交")])
    contract = _captcha_contract()
    guard = VerifyingCaptchaGuard(
        solver=solver,
        observer=observer,
        recognizer=make_recognizer(),
        captcha_condition=contract.captcha_condition,
        max_attempts=2,
    )
    adapter = FakeAdapter()
    result = TaskRunner(
        make_definition(contract, observer, adapter, captcha_guard=guard),
        FakeClock(),
    ).run()

    assert result.outcome is TaskOutcome.BLOCKED_BY_CAPTCHA
    assert solver.calls == 2
    assert adapter.advances == []
    assert any(
        event.kind == "captcha.verify_failed" or "仍然存在" in event.message
        for event in result.diagnostics
    )


def test_solver_failure_blocks_immediately() -> None:
    observer = QueueObserver([captcha_observation()])
    solver = FakeSolver([SolveResult(False, "布局异常，拒绝点选")])
    contract = _captcha_contract()
    guard = VerifyingCaptchaGuard(
        solver=solver,
        observer=observer,
        recognizer=make_recognizer(),
        captcha_condition=contract.captcha_condition,
        max_attempts=2,
    )
    adapter = FakeAdapter()
    result = TaskRunner(
        make_definition(contract, observer, adapter, captcha_guard=guard),
        FakeClock(),
    ).run()

    assert result.outcome is TaskOutcome.BLOCKED_BY_CAPTCHA
    assert result.outcome is not TaskOutcome.FAILED
    assert solver.calls == 1
    assert adapter.advances == []


def test_manual_guard_waits_for_human() -> None:
    context = make_context(captcha_observation())
    outcome = ManualCaptchaGuard().handle(context)
    assert outcome.resolution is CaptchaResolution.WAITING_FOR_HUMAN
    assert outcome.solved is False
