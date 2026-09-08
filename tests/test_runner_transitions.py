"""调度核心：状态转移、UNKNOWN 语义、恢复升级、致命错误。"""

from __future__ import annotations

from qqreader.contract.conditions import (
    Always,
    Never,
    feature,
    predicate,
    state_in,
)
from qqreader.contract.contract import FatalErrorSpec
from qqreader.contract.outcome import TaskOutcome
from qqreader.page.features import FeatureKind, FeatureSpec
from qqreader.page.states import PageState, RunState
from qqreader.recovery.policy import EscalationPolicy, RecoveryAction
from qqreader.runner.runner import RunnerConfig, TaskRunner
from tests.helpers import (
    FakeAdapter,
    PageFlowObserver,
    QueueObserver,
    ad_playing_observation,
    ad_result_observation,
    home_observation,
    make_contract,
    make_definition,
    reward_observation,
    PageObservation,
    FakeClock,
)


def _ad_like_contract(timeout_seconds: float = 60.0):
    return make_contract(
        name="ad_like",
        start_condition=state_in(PageState.HOME, PageState.REWARD_HOME),
        ready_condition=state_in(PageState.REWARD_HOME),
        progress_condition=state_in(
            PageState.AD_PLAYING, PageState.AD_RESULT, PageState.REWARD_HOME
        ),
        success_condition=feature(FeatureSpec(kind=FeatureKind.OCR, key="12/12")),
        timeout_seconds=timeout_seconds,
    )


def test_success_path_progresses_through_phases() -> None:
    observer = QueueObserver(
        [
            home_observation(),
            reward_observation(),
            ad_playing_observation(),
            ad_result_observation(),
            reward_observation(ocr=("12/12",)),
        ]
    )
    adapter = FakeAdapter()
    definition = make_definition(_ad_like_contract(), observer, adapter)

    result = TaskRunner(definition, FakeClock()).run()

    assert result.outcome is TaskOutcome.SUCCESS
    assert result.run_state is RunState.SUCCEEDED
    assert result.final_state is PageState.REWARD_HOME
    # 起点与就绪阶段不执行业务点击；进入 RUNNING 后才推进。
    assert adapter.advances == [PageState.AD_PLAYING, PageState.AD_RESULT]
    kinds = [event.kind for event in result.diagnostics]
    assert "phase.ready" in kinds
    assert "phase.running" in kinds
    assert "task.success" in kinds
    assert "run.finish" in kinds


def test_fatal_error_returns_failed() -> None:
    contract = make_contract(
        fatal_error=(
            FatalErrorSpec(
                name="device_offline",
                when=predicate(lambda ctx: ctx.observation.device_online is False),
            ),
        )
    )
    observer = QueueObserver([home_observation(device_online=False)])
    result = TaskRunner(make_definition(contract, observer, FakeAdapter()), FakeClock()).run()
    assert result.outcome is TaskOutcome.FAILED
    assert result.run_state is RunState.FAILED
    assert any(event.kind == "error.fatal" for event in result.diagnostics)


def test_unknown_never_fails_and_eventually_succeeds() -> None:
    contract = make_contract(
        name="unknown_then_ok",
        start_condition=state_in(PageState.HOME),
        ready_condition=state_in(PageState.REWARD_HOME),
        success_condition=feature(FeatureSpec(kind=FeatureKind.OCR, key="12/12")),
        timeout_seconds=30.0,
    )
    observer = QueueObserver(
        [
            PageObservation.empty(),
            PageObservation.empty(),
            home_observation(),
            reward_observation(ocr=("12/12",)),
        ]
    )
    result = TaskRunner(make_definition(contract, observer, FakeAdapter()), FakeClock()).run()
    assert result.outcome is TaskOutcome.SUCCESS
    assert any(event.kind == "page.unknown" for event in result.diagnostics)
    assert all(
        event.kind != "error.fatal" and event.kind != "run.error"
        for event in result.diagnostics
    )


def test_unknown_streak_triggers_recovery_not_failure() -> None:
    contract = make_contract(
        name="stuck_unknown",
        start_condition=Always(),
        ready_condition=Always(),
        progress_condition=Always(),
        success_condition=Never(),
        timeout_seconds=5.0,
    )
    observer = QueueObserver([PageObservation.empty()])
    adapter = FakeAdapter(on_advance=lambda ctx: ctx.clock.sleep(1.0, ctx.token))
    definition = make_definition(
        contract,
        observer,
        adapter,
        recovery=EscalationPolicy(max_rounds=1),
    )

    result = TaskRunner(
        definition,
        FakeClock(),
        config=RunnerConfig(recovery_pause_seconds=0.0),
    ).run()

    assert result.outcome is TaskOutcome.TIMEOUT
    assert adapter.recoveries == [
        RecoveryAction.RESCREENSHOT,
        RecoveryAction.REEVALUATE_STATE,
        RecoveryAction.DISMISS_POPUP,
    ]
    assert result.outcome is not TaskOutcome.FAILED


def test_progress_stall_triggers_recovery_and_only_fails_after_exhaustion() -> None:
    contract = make_contract(
        name="stall",
        start_condition=Always(),
        ready_condition=Always(),
        progress_condition=Never(),
        success_condition=Never(),
        timeout_seconds=20.0,
    )
    observer = QueueObserver([home_observation()])
    adapter = FakeAdapter(on_advance=lambda ctx: ctx.clock.sleep(1.0, ctx.token))
    definition = make_definition(
        contract, observer, adapter, recovery=EscalationPolicy(max_rounds=1)
    )

    result = TaskRunner(
        definition, FakeClock(), config=RunnerConfig(recovery_pause_seconds=0.0)
    ).run()

    # 卡死不会立即判失败：先走完整条恢复阶梯，阶梯耗尽且独立超时后才 FAILED。
    assert result.outcome is TaskOutcome.FAILED
    assert "恢复阶梯已耗尽" in result.reason
    assert adapter.recoveries[0] is RecoveryAction.RESCREENSHOT
    assert adapter.recoveries == list(EscalationPolicy(max_rounds=1).usable_ladder)
    assert any(event.kind == "progress.stall" for event in result.diagnostics)


def test_page_state_change_resets_recovery_ladder() -> None:
    contract = make_contract(
        name="reset_on_change",
        start_condition=Always(),
        ready_condition=Always(),
        progress_condition=Always(),
        success_condition=Never(),
        timeout_seconds=6.0,
    )
    # 页面由「恢复 / 推进」驱动翻转，而不是靠固定的观测脚本，
    # 这样即使页面确认阶梯会额外抓帧，也能稳定制造两次「状态变化」。
    observer = PageFlowObserver(
        {"unknown": PageObservation.empty(), "home": home_observation()},
        start="unknown",
    )

    def flip_page(_action, _context) -> None:
        observer.go("home" if observer.page == "unknown" else "unknown")

    def advance_and_flip(ctx) -> None:
        ctx.clock.sleep(1.0, ctx.token)
        observer.go("unknown")

    adapter = FakeAdapter(on_advance=advance_and_flip, on_recover=flip_page)
    definition = make_definition(
        contract, observer, adapter, recovery=EscalationPolicy(max_rounds=1)
    )
    result = TaskRunner(
        definition, FakeClock(), config=RunnerConfig(recovery_pause_seconds=0.0)
    ).run()

    assert result.outcome is TaskOutcome.TIMEOUT
    # 两次状态变化都让阶梯从头开始，因此两次恢复都是第一个动作。
    assert adapter.recoveries == [RecoveryAction.RESCREENSHOT, RecoveryAction.RESCREENSHOT]
    assert sum(
        1 for event in result.diagnostics if event.kind == "recovery.reset"
    ) >= 2


def test_unexpected_exception_returns_failed_with_diagnostics() -> None:
    class ExplodingObserver:
        def observe(self, context, *, deep: bool = False):
            raise RuntimeError("boom")

    contract = make_contract(name="exploding")
    result = TaskRunner(
        make_definition(contract, ExplodingObserver(), FakeAdapter()), FakeClock()
    ).run()
    assert result.outcome is TaskOutcome.FAILED
    assert any("boom" in event.message for event in result.diagnostics)
