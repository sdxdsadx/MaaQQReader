"""页面确认：识别不到目标时「先确认，再决定是否恢复」。

对应 AGENTS.md §3.6 与 QQR-5 / F-002 的判定顺序：

    重新截图 → 重新判断当前状态 → 尝试模板 B / OCR / 页面特征
    → 检查弹窗 → 检查验证码 → 必要时刷新当前状态 → 再决定是否恢复

本模块只做**确认**，不点击、不返回「目标不存在 / 任务失败」：

* 确认成功 → 返回确认到的页面状态；
* 确认失败 → ``needs_recovery=True``，由调度核心升级到恢复；
* 发现验证码 → ``captcha_detected=True``，由调度核心转入验证码专用流程。

每一次尝试都写入 :class:`ConfirmationAttempt`，让 ``TaskResult.diagnostics``
能回答 QQR-5 要求的「尝试了哪些特征、各自结果」。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Optional, Tuple

from ..contract.conditions import Condition, build_popup_condition
from ..contract.outcome import DiagnosticEvent
from ..page.observation import PageObservation
from ..page.recognizer import PageStateRecognizer, StateDecision
from ..page.states import PageState

if TYPE_CHECKING:  # pragma: no cover - 仅类型标注
    from ..runtime.context import TaskContext
    from ..runtime.observer import PageObserver


class ConfirmationStep(str, Enum):
    """页面确认阶梯中的一步。"""

    RESCREENSHOT = "RESCREENSHOT"
    REEVALUATE_STATE = "REEVALUATE_STATE"
    EXPAND_FEATURES = "EXPAND_FEATURES"
    CHECK_POPUP = "CHECK_POPUP"
    CHECK_CAPTCHA = "CHECK_CAPTCHA"
    REFRESH_STATE = "REFRESH_STATE"


#: QQR-5 / §3.6 要求的完整确认顺序。
CONFIRMATION_LADDER: Tuple[ConfirmationStep, ...] = (
    ConfirmationStep.RESCREENSHOT,
    ConfirmationStep.REEVALUATE_STATE,
    ConfirmationStep.EXPAND_FEATURES,
    ConfirmationStep.CHECK_POPUP,
    ConfirmationStep.CHECK_CAPTCHA,
    ConfirmationStep.REFRESH_STATE,
)


@dataclass(frozen=True)
class ConfirmationConfig:
    """确认阶梯开关。

    全部默认开启，保证「第一次识别失败」也会走完整确认流程，而不是被
    当作任务失败。
    """

    expand_features: bool = True
    check_popup: bool = True
    check_captcha: bool = True
    refresh_state: bool = True

    def steps(self) -> Tuple[ConfirmationStep, ...]:
        steps = [ConfirmationStep.RESCREENSHOT, ConfirmationStep.REEVALUATE_STATE]
        if self.expand_features:
            steps.append(ConfirmationStep.EXPAND_FEATURES)
        if self.check_popup:
            steps.append(ConfirmationStep.CHECK_POPUP)
        if self.check_captcha:
            steps.append(ConfirmationStep.CHECK_CAPTCHA)
        if self.refresh_state:
            steps.append(ConfirmationStep.REFRESH_STATE)
        return tuple(steps)


@dataclass(frozen=True)
class ConfirmationAttempt:
    """页面确认的一步及其证据。"""

    index: int
    step: ConfirmationStep
    at: float
    confirmed: bool
    state: PageState
    confidence: float
    note: str
    observation: Optional[PageObservation] = None
    decision: Optional[StateDecision] = None
    feature_report: Tuple[str, ...] = ()

    def summary(self) -> str:
        return (
            f"#{self.index} {self.step.value} state={self.state.value} "
            f"confirmed={self.confirmed} confidence={self.confidence:.3f} — {self.note}"
        )


@dataclass(frozen=True)
class ConfirmationResult:
    """一次页面确认的完整结论。"""

    confirmed: bool
    state: PageState
    confidence: float
    attempts: Tuple[ConfirmationAttempt, ...]
    captcha_detected: bool = False
    popup_detected: bool = False
    reason: str = ""

    @property
    def needs_recovery(self) -> bool:
        """未确认且不是验证码时，只能走恢复，绝不能判定任务失败。"""
        return not self.confirmed and not self.captcha_detected

    @property
    def observation(self) -> Optional[PageObservation]:
        for attempt in reversed(self.attempts):
            if attempt.observation is not None:
                return attempt.observation
        return None

    @property
    def decision(self) -> Optional[StateDecision]:
        for attempt in reversed(self.attempts):
            if attempt.decision is not None:
                return attempt.decision
        return None

    def steps(self) -> Tuple[ConfirmationStep, ...]:
        return tuple(a.step for a in self.attempts)

    def feature_report(self) -> Tuple[str, ...]:
        """最后一步的「每个候选状态分别命中了哪些特征」。"""
        for attempt in reversed(self.attempts):
            if attempt.feature_report:
                return attempt.feature_report
        return ()

    def diagnostics(self) -> Tuple[DiagnosticEvent, ...]:
        events = []
        for attempt in self.attempts:
            events.append(
                DiagnosticEvent(
                    at=attempt.at,
                    kind=f"CONFIRM_{attempt.step.value}",
                    message=f"{attempt.summary()}",
                    data={
                        "confirmed": attempt.confirmed,
                        "confidence": round(attempt.confidence, 3),
                    },
                )
            )
        if not self.confirmed and not self.captcha_detected:
            events.append(
                DiagnosticEvent(
                    at=self.attempts[-1].at if self.attempts else 0.0,
                    kind="CONFIRM_UNRESOLVED",
                    message=(
                        "页面确认结束仍未确认任何状态：按 QQR-5 不得判定任务失败，"
                        "转交升级式恢复"
                    ),
                    data={
                        "steps": [s.value for s in self.steps()],
                        "popup_detected": self.popup_detected,
                    },
                )
            )
        return tuple(events)

    def render(self) -> str:
        lines = [
            f"页面确认: confirmed={self.confirmed} state={self.state.value} "
            f"confidence={self.confidence:.3f}"
        ]
        lines.append(f"reason={self.reason}")
        lines.append(f"popup_detected={self.popup_detected} captcha_detected={self.captcha_detected}")
        for attempt in self.attempts:
            lines.append("  " + attempt.summary())
            for line in attempt.feature_report:
                lines.append("      " + line)
        return "\n".join(lines)


class PageConfirmer:
    """把「识别不到」升级为「多特征重新确认」。"""

    def __init__(
        self,
        observer: "PageObserver",
        recognizer: PageStateRecognizer,
        *,
        captcha_condition: Optional[Condition] = None,
        popup_condition: Optional[Condition] = None,
        config: ConfirmationConfig = ConfirmationConfig(),
    ) -> None:
        self._observer = observer
        self._recognizer = recognizer
        self._captcha_condition = captcha_condition
        self._popup_condition = popup_condition or build_popup_condition()
        self._config = config

    def confirm(
        self,
        context: "TaskContext",
        *,
        observation: Optional[PageObservation] = None,
        decision: Optional[StateDecision] = None,
    ) -> ConfirmationResult:
        """执行确认阶梯；无论结果如何都不返回「任务失败」。"""

        attempts = []
        captcha_detected = False
        popup_detected = False

        def record(
            step: ConfirmationStep,
            obs: Optional[PageObservation],
            dec: Optional[StateDecision],
            note: str,
        ) -> None:
            if obs is not None and dec is not None:
                context.update_observation(obs, dec)
            attempts.append(
                ConfirmationAttempt(
                    index=len(attempts) + 1,
                    step=step,
                    at=context.now,
                    confirmed=bool(dec is not None and dec.is_confirmed),
                    state=dec.state if dec is not None else PageState.UNKNOWN,
                    confidence=dec.confidence if dec is not None else 0.0,
                    note=note,
                    observation=obs,
                    decision=dec,
                    feature_report=self._feature_report(dec),
                )
            )

        def refresh(step: ConfirmationStep, *, deep: bool, note: str) -> Optional[StateDecision]:
            obs = self._observer.observe(context, deep=deep)
            dec = self._recognizer.evaluate(obs)
            record(step, obs, dec, note)
            return dec

        # 调用方通常已经做了一次未确认观测；这里从「重新截图」重新开始，
        # 保证确认结论基于一帧新的、独立的证据。
        current = refresh(
            ConfirmationStep.RESCREENSHOT,
            deep=False,
            note="重新截图并重新判断",
        )
        if current is not None and current.state is PageState.CAPTCHA:
            return self._captcha_result(current, attempts, popup_detected)
        if current is not None and current.is_confirmed:
            return self._confirmed(current, attempts, popup_detected)

        # 重新判断当前状态：显式记录「未确认 ≠ 目标不存在」。
        latest = attempts[-1]
        record(
            ConfirmationStep.REEVALUATE_STATE,
            latest.observation,
            latest.decision,
            "重新判断当前状态：未达到确认阈值，结果只能是 UNKNOWN / 继续确认，"
            "不得推导为目标不存在或任务失败",
        )

        if self._config.expand_features:
            current = refresh(
                ConfirmationStep.EXPAND_FEATURES,
                deep=True,
                note="常规特征不足，追加模板 B / 备用 OCR / 页面结构特征",
            )
            if current is not None and current.state is PageState.CAPTCHA:
                return self._captcha_result(current, attempts, popup_detected)
            if current is not None and current.is_confirmed:
                return self._confirmed(current, attempts, popup_detected)

        if self._config.check_popup:
            popup = self._popup_condition.evaluate(context)
            popup_detected = popup.satisfied
            record(
                ConfirmationStep.CHECK_POPUP,
                attempts[-1].observation,
                attempts[-1].decision,
                f"检查弹窗遮挡: {popup.reason}",
            )

        if self._config.check_captcha:
            captcha = self._captcha_condition.evaluate(context) if self._captcha_condition else None
            state_is_captcha = context.state is PageState.CAPTCHA
            captcha_detected = state_is_captcha or bool(captcha and captcha.satisfied)
            reason = (
                "状态=CAPTCHA"
                if state_is_captcha
                else (captcha.reason if captcha is not None else "未配置验证码条件")
            )
            record(
                ConfirmationStep.CHECK_CAPTCHA,
                attempts[-1].observation,
                attempts[-1].decision,
                f"检查验证码: {reason}",
            )
            if captcha_detected:
                return ConfirmationResult(
                    confirmed=False,
                    state=context.state,
                    confidence=attempts[-1].confidence,
                    attempts=tuple(attempts),
                    captcha_detected=True,
                    popup_detected=popup_detected,
                    reason="确认过程中检测到验证码，转入验证码专用流程（不是任务失败）",
                )

        if self._config.refresh_state:
            current = refresh(
                ConfirmationStep.REFRESH_STATE,
                deep=True,
                note="必要时刷新当前状态后再决定是否恢复",
            )
            if current is not None and current.state is PageState.CAPTCHA:
                return self._captcha_result(current, attempts, popup_detected)
            if current is not None and current.is_confirmed:
                return self._confirmed(current, attempts, popup_detected)

        last = attempts[-1]
        return ConfirmationResult(
            confirmed=False,
            state=last.state,
            confidence=last.confidence,
            attempts=tuple(attempts),
            captcha_detected=False,
            popup_detected=popup_detected,
            reason=(
                "确认阶梯全部走完仍未确认任何状态；"
                "这是识别失败，不是任务失败，交由升级式恢复处理"
            ),
        )

    # ------------------------------------------------------------------ 内部

    def _captcha_result(
        self,
        decision: StateDecision,
        attempts: list,
        popup_detected: bool,
    ) -> ConfirmationResult:
        """识别到验证码状态：转验证码流程，绝不当作确认成功或任务失败。"""
        return ConfirmationResult(
            confirmed=False,
            state=PageState.CAPTCHA,
            confidence=decision.confidence,
            attempts=tuple(attempts),
            captcha_detected=True,
            popup_detected=popup_detected,
            reason="确认过程中识别到验证码状态，转入验证码专用流程（不是任务失败）",
        )

    def _confirmed(
        self,
        decision: StateDecision,
        attempts: list,
        popup_detected: bool,
    ) -> ConfirmationResult:
        return ConfirmationResult(
            confirmed=True,
            state=decision.state,
            confidence=decision.confidence,
            attempts=tuple(attempts),
            captcha_detected=False,
            popup_detected=popup_detected,
            reason=f"页面确认成功: {decision.state.value}（{decision.reason}）",
        )

    @staticmethod
    def _feature_report(decision: Optional[StateDecision]) -> Tuple[str, ...]:
        if decision is None:
            return ()
        lines = []
        for candidate in decision.candidates:
            matched = ", ".join(
                f"{m.kind.value}:{m.spec.key or (m.spec.candidates[0] if m.spec.candidates else '?')}"
                for m in candidate.matched
            ) or "无"
            missing = ", ".join(
                f"{m.kind.value}:{m.spec.key or (m.spec.candidates[0] if m.spec.candidates else '?')}"
                f"(score={m.score:.2f},阈值={m.spec.threshold:.2f})"
                for m in candidate.missing_required
            ) or "无"
            lines.append(
                f"{candidate.state.value} score={candidate.score:.3f} "
                f"matched={candidate.matched_count}/{candidate.total_count} "
                f"required_ok={candidate.required_ok} 命中=[{matched}] 缺失必需=[{missing}]"
            )
        return tuple(lines)
