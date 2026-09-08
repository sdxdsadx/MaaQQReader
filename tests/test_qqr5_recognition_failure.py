"""QQR-5 / F-002：识别失败先确认与恢复，禁止「连续几次 Match False 即失败」。

这些测试锁定**调度核心**（而不是单独的确认组件）的行为：

* 连续多帧无法识别时，先在页面上做多特征确认，再决定是否恢复；
* ``UNKNOWN`` 上绝不点击、绝不判定任务失败；
* 只有「确认 → 恢复阶梯耗尽 → 独立超时」之后才允许 ``FAILED``；
* 确认过程中发现弹窗 / 验证码时走各自的专用流程；
* 识别失败必须留下「尝试了哪些特征、各自结果」的诊断。
"""

from __future__ import annotations

from collections import deque
from typing import Sequence

from qqreader.contract.conditions import Always, Never, feature, state_in
from qqreader.contract.outcome import TaskOutcome
from qqreader.page.features import FeatureKind, FeatureSpec
from qqreader.page.observation import PageObservation
from qqreader.page.states import PageState
from qqreader.recovery.policy import EscalationPolicy, RecoveryAction
from qqreader.runner.runner import TaskRunner
from tests.helpers import (
    FakeAdapter,
    FakeClock,
    StubCaptchaGuard,
    captcha_observation,
    make_contract,
    make_definition,
    reward_observation,
)


class RecordingObserver:
    """按脚本返回观测，并记录每次是否请求了深度证据；脚本耗尽后重复最后一帧。"""

    def __init__(self, script: Sequence[PageObservation]) -> None:
        if not script:
            raise ValueError("script 不能为空")
        self._queue = deque(script)
        self._last = script[-1]
        self.deep_flags = []

    def observe(self, context, *, deep: bool = False) -> PageObservation:  # noqa: ANN001
        self.deep_flags.append(deep)
        if self._queue:
            self._last = self._queue.popleft()
        return self._last


def _ad_contract(timeout_seconds: float = 30.0):
    """模拟广告任务：起点/就绪/推进/成功条件都齐备。"""
    return make_contract(
        name="ad_scenario_b",
        start_condition=state_in(PageState.HOME, PageState.REWARD_HOME),
        ready_condition=state_in(PageState.REWARD_HOME),
        progress_condition=state_in(
            PageState.AD_PLAYING, PageState.AD_RESULT, PageState.REWARD_HOME
        ),
        success_condition=feature(FeatureSpec(kind=FeatureKind.OCR, key="12/12")),
        timeout_seconds=timeout_seconds,
    )


def _stuck_contract(timeout_seconds: float):
    """永远无法完成、也永远无法确认的契约。"""
    return make_contract(
        name=f"stuck_{timeout_seconds:g}",
        start_condition=Always(),
        ready_condition=Always(),
        progress_condition=Always(),
        success_condition=Never(),
        timeout_seconds=timeout_seconds,
    )


def test_scenario_b_repeated_match_false_confirms_then_succeeds() -> None:
    """验收场景 B：前几帧识别失败，不得判失败；确认页面后继续完成。"""
    observer = RecordingObserver(
        [PageObservation.empty()] * 5 + [reward_observation(ocr=("12/12",))]
    )
    adapter = FakeAdapter()
    result = TaskRunner(
        make_definition(_ad_contract(), observer, adapter), FakeClock()
    ).run()

    assert result.outcome is TaskOutcome.SUCCESS
    assert result.final_state is PageState.REWARD_HOME
    # UNKNOWN 上绝不点击：本场景确认成功后无需任何业务推进即可满足成功条件。
    assert adapter.advances == []

    kinds = [event.kind for event in result.diagnostics]
    assert "page.unknown" in kinds
    assert "CONFIRM_EXPAND_FEATURES" in kinds
    assert "page.confirmed" in kinds
    # 常规特征不足后才请求深度证据（模板 B / 备用 OCR / 结构特征）。
    assert True in observer.deep_flags
    # 识别失败必须留下「尝试了哪些特征、各自结果」。
    reports = [event for event in result.diagnostics if event.kind == "page.features"]
    assert reports
    lines = [line for event in reports for line in event.data["features"]]
    assert any("缺失必需=" in line for line in lines)
    assert any("score=" in line for line in lines)
    assert not any(
        event.kind in ("error.fatal", "run.error") for event in result.diagnostics
    )


def test_repeated_match_false_times_out_instead_of_failing_early() -> None:
    """连续 Match False 只会触发确认与恢复；在阶梯耗尽前绝不 FAILED。"""
    observer = RecordingObserver([PageObservation.empty()])
    adapter = FakeAdapter()
    result = TaskRunner(
        make_definition(
            _stuck_contract(4.0),
            observer,
            adapter,
            recovery=EscalationPolicy(max_rounds=1),
        ),
        FakeClock(),
    ).run()

    assert result.outcome is TaskOutcome.TIMEOUT
    assert result.outcome is not TaskOutcome.FAILED
    assert adapter.advances == []
    # 已经升级到恢复动作，而不是把几次未识别当成任务失败。
    assert adapter.recoveries
    kinds = [event.kind for event in result.diagnostics]
    assert "CONFIRM_UNRESOLVED" in kinds
    assert "page.features" in kinds


def test_failure_requires_recovery_exhaustion_and_timeout() -> None:
    """只有确认 + 恢复阶梯耗尽 + 独立超时之后，才允许 FAILED。"""
    observer = RecordingObserver([PageObservation.empty()])
    adapter = FakeAdapter()
    policy = EscalationPolicy(max_rounds=1)
    result = TaskRunner(
        make_definition(
            _stuck_contract(12.0), observer, adapter, recovery=policy
        ),
        FakeClock(),
    ).run()

    assert result.outcome is TaskOutcome.FAILED
    assert "恢复阶梯已耗尽" in result.reason
    # 失败前确实走完了整条恢复阶梯。
    assert adapter.recoveries == list(policy.usable_ladder)
    assert adapter.advances == []
    kinds = [event.kind for event in result.diagnostics]
    assert "recovery.exhausted" in kinds
    assert "page.features" in kinds


def test_popup_during_confirmation_uses_targeted_dismiss() -> None:
    """确认阶段发现弹窗遮挡：定向关闭，不占用恢复阶梯，也绝不点击业务按钮。"""
    popup = PageObservation(templates={"popup.close": 0.9})
    observer = RecordingObserver([popup])
    adapter = FakeAdapter()
    result = TaskRunner(
        make_definition(
            _stuck_contract(3.0),
            observer,
            adapter,
            recovery=EscalationPolicy(max_rounds=1),
        ),
        FakeClock(),
    ).run()

    assert adapter.advances == []
    assert adapter.recoveries
    # 第一次先定向关闭弹窗；弹窗反复出现后交回恢复阶梯继续升级。
    assert adapter.recoveries[0] is RecoveryAction.DISMISS_POPUP
    assert RecoveryAction.DISMISS_POPUP in adapter.recoveries
    kinds = [event.kind for event in result.diagnostics]
    assert "CONFIRM_CHECK_POPUP" in kinds


def test_captcha_discovered_during_confirmation_blocks_task() -> None:
    """初始帧只是 UNKNOWN，确认阶段才暴露验证码：转验证码流程，不是失败。"""
    observer = RecordingObserver(
        [PageObservation.empty(), PageObservation.empty(), captcha_observation()]
    )
    adapter = FakeAdapter()
    guard = StubCaptchaGuard()
    result = TaskRunner(
        make_definition(
            _stuck_contract(30.0), observer, adapter, captcha_guard=guard
        ),
        FakeClock(),
    ).run()

    assert result.outcome is TaskOutcome.BLOCKED_BY_CAPTCHA
    assert result.outcome is not TaskOutcome.FAILED
    assert guard.calls == 1
    # 验证码期间不得点击、不得进入普通恢复。
    assert adapter.advances == []
    assert adapter.recoveries == []


def test_task_definition_can_inject_confirmer() -> None:
    """调度核心优先使用 ``TaskDefinition.confirmer``，便于替换与测试。"""
    from qqreader.page.states import PageState
    from qqreader.runner.confirmation import ConfirmationResult

    class StubConfirmer:
        def __init__(self) -> None:
            self.calls = 0

        def confirm(self, context, *, observation=None, decision=None):  # noqa: ANN001
            self.calls += 1
            return ConfirmationResult(
                confirmed=False,
                state=PageState.UNKNOWN,
                confidence=0.0,
                attempts=(),
                reason="stub：故意不确认，验证注入点生效",
            )

    stub = StubConfirmer()
    observer = RecordingObserver([PageObservation.empty()])
    adapter = FakeAdapter()
    result = TaskRunner(
        make_definition(
            _stuck_contract(2.0),
            observer,
            adapter,
            recovery=EscalationPolicy(max_rounds=1),
            confirmer=stub,
        ),
        FakeClock(),
    ).run()

    assert stub.calls > 0
    assert result.outcome is TaskOutcome.TIMEOUT
