"""任务契约与装配：8 字段、默认注册表、适配器安全边界。"""

from __future__ import annotations

import json

import pytest

from qqreader.captcha.guard import ManualCaptchaGuard, VerifyingCaptchaGuard
from qqreader.captcha.slide import SlideCaptchaSolver
from qqreader.config import ConfigError, loads_config
from qqreader.contract.contract import CONTRACT_FIELDS, TimeoutSpec
from qqreader.page.feature_keys import DEFAULT_FEATURE_KEYS
from qqreader.page.observation import PageObservation
from qqreader.page.states import PageState, RunState
from qqreader.recovery.policy import EscalationPolicy
from qqreader.runner.runner import PHASE_KEY, RunPhase
from qqreader.tasks import (
    AD_TASK_NAME,
    GAME_TASK_NAME,
    ActionKind,
    PlannedTaskAdapter,
    build_ad_action_plan,
    build_ad_contract,
    build_ad_definition,
    build_default_registry,
    build_game_action_plan,
    build_game_contract,
    feature_key,
)
from qqreader.tasks.plan import Action
from tests.helpers import (
    QQ,
    QueueObserver,
    SimulatedDevice,
    home_observation,
    make_context,
    make_recognizer,
)

EXPECTED_FIELDS = (
    "start_condition",
    "ready_condition",
    "progress_condition",
    "captcha_condition",
    "success_condition",
    "recoverable_error",
    "fatal_error",
    "timeout",
)


def test_contract_fields_match_agents_spec() -> None:
    assert tuple(CONTRACT_FIELDS) == EXPECTED_FIELDS
    assert tuple(build_ad_contract().field_report().keys()) == EXPECTED_FIELDS


@pytest.mark.parametrize(
    "builder", [build_ad_contract, build_game_contract], ids=["ad", "game"]
)
def test_contract_defines_all_eight_fields(builder) -> None:
    contract = builder()
    report = contract.field_report()
    assert tuple(report.keys()) == EXPECTED_FIELDS
    for field in EXPECTED_FIELDS:
        assert getattr(contract, field) is not None, f"{contract.name}.{field} 未定义"
    assert isinstance(contract.timeout, TimeoutSpec)
    assert contract.timeout.seconds > 0
    assert len(contract.recoverable_error) >= 1
    assert len(contract.fatal_error) >= 1
    assert contract.start_condition.describe()
    assert contract.ready_condition.describe()
    assert contract.progress_condition.describe()
    assert contract.captcha_condition.describe()
    assert contract.success_condition.describe()


def test_ad_and_game_have_distinct_names() -> None:
    assert build_ad_contract().name == AD_TASK_NAME
    assert build_game_contract().name == GAME_TASK_NAME
    assert AD_TASK_NAME != GAME_TASK_NAME


def test_timeout_spec_rejects_non_positive() -> None:
    from qqreader.errors import ContractViolation

    with pytest.raises(ContractViolation):
        TimeoutSpec(0)


@pytest.mark.parametrize(
    "plan_builder,states",
    [
        (
            build_ad_action_plan,
            (
                PageState.HOME,
                PageState.REWARD_HOME,
                PageState.AD_PLAYING,
                PageState.AD_RESULT,
            ),
        ),
        (
            build_game_action_plan,
            (
                PageState.HOME,
                PageState.REWARD_HOME,
                PageState.GAME_LOADING,
                PageState.GAME_RUNNING,
                PageState.GAME_RESULT,
            ),
        ),
    ],
    ids=["ad", "game"],
)
def test_action_plan_covers_flow_and_is_safe_on_unknown(plan_builder, states) -> None:
    plan = plan_builder()
    for state in states:
        assert state in plan.actions, f"计划缺少状态动作: {state.value}"
    assert plan.action_for(PageState.UNKNOWN).kind is ActionKind.REOBSERVE
    # 验证码状态绝不允许落在普通点击动作上。
    assert plan.action_for(PageState.CAPTCHA).kind is ActionKind.REOBSERVE


def test_default_registry_registers_ad_and_game() -> None:
    registry = build_default_registry(
        QueueObserver([home_observation()]), SimulatedDevice()
    )
    assert registry.names() == (AD_TASK_NAME, GAME_TASK_NAME)
    assert AD_TASK_NAME in registry
    assert GAME_TASK_NAME in registry


def test_default_captcha_guard_uses_slide_solver() -> None:
    definition = build_ad_definition(
        DEFAULT_FEATURE_KEYS,
        QueueObserver([home_observation()]),
        SimulatedDevice(),
        EscalationPolicy(),
        make_recognizer(),
    )
    assert isinstance(definition.captcha_guard, VerifyingCaptchaGuard)
    assert isinstance(definition.captcha_guard._solver, SlideCaptchaSolver)


def test_planned_adapter_never_taps_on_unknown() -> None:
    device = SimulatedDevice()
    adapter = PlannedTaskAdapter(
        device=device,
        plan=build_ad_action_plan(),
        expected_package=QQ,
        popup_feature=feature_key(DEFAULT_FEATURE_KEYS, DEFAULT_FEATURE_KEYS.popup_close),
    )
    context = make_context(PageObservation.empty(), run_state=RunState.RUNNING)
    context.data[PHASE_KEY] = RunPhase.RUNNING.value

    step = adapter.advance(context)

    assert step.actions == (ActionKind.REOBSERVE.value,)
    assert step.progress is False
    assert device.calls == []


def test_planned_adapter_bootstraps_only_once_in_start() -> None:
    device = SimulatedDevice()
    adapter = PlannedTaskAdapter(
        device=device,
        plan=build_ad_action_plan(),
        expected_package=QQ,
        popup_feature=feature_key(DEFAULT_FEATURE_KEYS, DEFAULT_FEATURE_KEYS.popup_close),
    )
    context = make_context(PageObservation.empty(), run_state=RunState.STARTING)
    context.data[PHASE_KEY] = RunPhase.START.value

    first = adapter.advance(context)
    second = adapter.advance(context)

    assert first.actions == (f"{ActionKind.LAUNCH_APP.value}:{QQ}",)
    assert device.calls == [("launch_app", QQ)]
    assert second.actions == (ActionKind.REOBSERVE.value,)
    assert device.calls == [("launch_app", QQ)]


def test_planned_adapter_taps_mapped_feature() -> None:
    device = SimulatedDevice()
    adapter = PlannedTaskAdapter(
        device=device,
        plan=build_ad_action_plan(),
        expected_package=QQ,
        popup_feature=feature_key(DEFAULT_FEATURE_KEYS, DEFAULT_FEATURE_KEYS.popup_close),
    )
    context = make_context(home_observation(), run_state=RunState.RUNNING)
    context.data[PHASE_KEY] = RunPhase.RUNNING.value

    step = adapter.advance(context)

    assert device.calls == [
        (
            "tap_feature",
            feature_key(
                DEFAULT_FEATURE_KEYS, DEFAULT_FEATURE_KEYS.home_ocr_reward_entry
            ),
        )
    ]
    assert step.progress is True


def test_recovery_action_mapping_uses_ladder() -> None:
    from qqreader.recovery.policy import RecoveryAction

    device = SimulatedDevice()
    adapter = PlannedTaskAdapter(
        device=device,
        plan=build_ad_action_plan(),
        expected_package=QQ,
        popup_feature=feature_key(DEFAULT_FEATURE_KEYS, DEFAULT_FEATURE_KEYS.popup_close),
    )
    context = make_context(home_observation(), run_state=RunState.RECOVERING)

    adapter.recover(RecoveryAction.PRESS_BACK, context)
    adapter.recover(RecoveryAction.RESTART_APP, context)

    assert device.calls == [
        ("press_back",),
        ("stop_app", QQ),
        ("launch_app", QQ),
    ]


def test_action_validation() -> None:
    from qqreader.errors import ContractViolation

    with pytest.raises(ContractViolation):
        Action(ActionKind.TAP_FEATURE)
    with pytest.raises(ContractViolation):
        Action(ActionKind.WAIT, seconds=-1)


def _config_with(tasks: dict, captcha: dict | None = None):
    return loads_config(
        json.dumps(
            {
                "version": 1,
                "machine": {
                    "adb_path": "C:\\tools\\adb.exe",
                    "adb_address": "127.0.0.1:16384",
                },
                "captcha": captcha or {"solver": "manual"},
                "tasks": tasks,
            }
        )
    )


def test_default_registry_uses_config_enabled_and_timeout() -> None:
    config = _config_with(
        {
            "DailyAdFlow": {"enabled": True, "timeout_seconds": 99},
            "DailyGameFlow": {"enabled": False},
        }
    )
    registry = build_default_registry(
        QueueObserver([home_observation()]), SimulatedDevice(), config=config
    )
    assert registry.names() == (AD_TASK_NAME,)
    assert registry.get(AD_TASK_NAME).contract.timeout.seconds == 99


def test_default_registry_rejects_auto_solver_without_guard() -> None:
    config = _config_with({}, captcha={"solver": "ddddocr"})
    with pytest.raises(ConfigError, match="captcha_guard"):
        build_default_registry(
            QueueObserver([home_observation()]), SimulatedDevice(), config=config
        )


def test_default_registry_accepts_injected_guard_for_auto_solver() -> None:
    config = _config_with({}, captcha={"solver": "ddddocr"})
    registry = build_default_registry(
        QueueObserver([home_observation()]),
        SimulatedDevice(),
        config=config,
        captcha_guard=ManualCaptchaGuard(),
    )
    assert AD_TASK_NAME in registry
