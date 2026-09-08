"""页面确认阶梯：识别不到时「先确认，再决定是否恢复」（AGENTS.md §3.6）。"""

from __future__ import annotations

from qqreader.contract.conditions import Always
from qqreader.page.observation import PageObservation
from qqreader.page.states import PageState
from qqreader.runner.confirmation import (
    CONFIRMATION_LADDER,
    ConfirmationConfig,
    ConfirmationStep,
    PageConfirmer,
)
from tests.helpers import (
    QueueObserver,
    captcha_observation,
    home_observation,
    make_context,
    make_recognizer,
)


class DeepRecordingObserver:
    """记录每次观测是否请求了深度证据。"""

    def __init__(self, script) -> None:
        self._inner = QueueObserver(script)
        self.deep_flags = []

    def observe(self, context, *, deep: bool = False):
        self.deep_flags.append(deep)
        return self._inner.observe(context, deep=deep)


def test_confirmation_ladder_order_matches_spec() -> None:
    assert CONFIRMATION_LADDER == (
        ConfirmationStep.RESCREENSHOT,
        ConfirmationStep.REEVALUATE_STATE,
        ConfirmationStep.EXPAND_FEATURES,
        ConfirmationStep.CHECK_POPUP,
        ConfirmationStep.CHECK_CAPTCHA,
        ConfirmationStep.REFRESH_STATE,
    )


def test_confirm_succeeds_on_first_frame() -> None:
    observer = QueueObserver([home_observation()])
    result = PageConfirmer(observer, make_recognizer()).confirm(
        make_context(PageObservation.empty())
    )
    assert result.confirmed is True
    assert result.state is PageState.HOME
    assert result.steps() == (ConfirmationStep.RESCREENSHOT,)
    assert result.needs_recovery is False


def test_confirm_expands_features_before_recovery() -> None:
    observer = DeepRecordingObserver(
        [PageObservation.empty(), home_observation()]
    )
    result = PageConfirmer(observer, make_recognizer()).confirm(
        make_context(PageObservation.empty())
    )
    assert result.confirmed is True
    assert result.state is PageState.HOME
    assert result.steps() == (
        ConfirmationStep.RESCREENSHOT,
        ConfirmationStep.REEVALUATE_STATE,
        ConfirmationStep.EXPAND_FEATURES,
    )
    # 常规观测失败后才请求深度证据（模板 B / 备用 OCR / 结构特征）。
    assert observer.deep_flags == [False, True]


def test_unresolved_confirmation_is_recovery_not_failure() -> None:
    observer = QueueObserver([PageObservation.empty()])
    result = PageConfirmer(observer, make_recognizer()).confirm(
        make_context(PageObservation.empty())
    )
    assert result.confirmed is False
    assert result.captcha_detected is False
    assert result.needs_recovery is True
    assert "不是任务失败" in result.reason
    kinds = [event.kind for event in result.diagnostics()]
    assert "CONFIRM_UNRESOLVED" in kinds


def test_confirmed_captcha_state_is_captcha_not_confirmed() -> None:
    observer = QueueObserver([captcha_observation()])
    result = PageConfirmer(observer, make_recognizer()).confirm(
        make_context(PageObservation.empty())
    )
    assert result.confirmed is False
    assert result.captcha_detected is True
    assert result.state is PageState.CAPTCHA
    assert result.needs_recovery is False
    assert "验证码" in result.reason


def test_captcha_condition_is_checked_late_in_ladder() -> None:
    observer = QueueObserver([PageObservation.empty()])
    result = PageConfirmer(
        observer, make_recognizer(), captcha_condition=Always()
    ).confirm(make_context(PageObservation.empty()))
    assert result.captcha_detected is True
    assert result.needs_recovery is False
    assert ConfirmationStep.CHECK_CAPTCHA in result.steps()


def test_popup_detection_is_recorded() -> None:
    popup = PageObservation(templates={"popup.close": 0.9})
    observer = QueueObserver([popup])
    result = PageConfirmer(observer, make_recognizer()).confirm(
        make_context(PageObservation.empty())
    )
    assert result.confirmed is False
    assert result.popup_detected is True
    assert result.needs_recovery is True
    assert ConfirmationStep.CHECK_POPUP in result.steps()


def test_confirmation_config_can_disable_steps() -> None:
    config = ConfirmationConfig(
        expand_features=False,
        check_popup=False,
        check_captcha=False,
        refresh_state=False,
    )
    assert config.steps() == (
        ConfirmationStep.RESCREENSHOT,
        ConfirmationStep.REEVALUATE_STATE,
    )


def test_confirm_updates_context_evidence() -> None:
    context = make_context(PageObservation.empty())
    observer = QueueObserver([home_observation()])
    result = PageConfirmer(observer, make_recognizer()).confirm(context)
    assert context.state is PageState.HOME
    assert context.observation is result.observation
