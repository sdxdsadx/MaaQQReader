"""通用任务执行器（调度核心）。

这是唯一一处「按契约跑任务」的地方，**不含任何任务名特判**：

* 阶段推进：``start_condition`` → ``ready_condition`` → ``success_condition``；
* 每一步都先观测、再由识别器判断页面状态；
* 验证码优先级最高：一旦检测到 ``CAPTCHA``，正常推进立即暂停，
  只走验证码守卫，**绝不**进入普通恢复或继续点击；
* ``UNKNOWN`` 只触发重新判断 / 恢复，绝不判失败；
* 只有「恢复阶梯耗尽 + 独立超时」才允许 ``FAILED``；
* 取消是独立结果 ``CANCELLED``，不是失败。

领域行为全部由 ``TaskAdapter`` 提供，因此广告、游戏以及未来的阅读/听书
任务共用同一个执行器。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Tuple

from ..contract.conditions import ConditionResult
from ..contract.contract import FatalErrorSpec, RecoverableErrorSpec
from ..contract.outcome import DiagnosticEvent, TaskOutcome, TaskResult
from ..errors import Cancelled
from ..page.recognizer import StateDecision
from ..page.states import PageState, RunState
from ..recovery.policy import RecoveryAction
from ..runtime.clock import CancellationToken, Clock
from ..runtime.context import TaskContext
from .confirmation import ConfirmationConfig, PageConfirmer, feature_report
from .definition import TaskDefinition

#: 当前执行阶段在 ``TaskContext.data`` 中的键；适配器可据此做安全的引导动作。
PHASE_KEY = "phase"


@dataclass(frozen=True)
class RunnerConfig:
    """执行器调参（不进入任务契约，属于工程参数）。"""

    #: 单次任务允许的最大循环次数（防止适配器/恢复策略出现死循环）。
    max_steps: int = 2000
    #: 连续多少次 progress_condition 不满足后升级恢复（绝不直接判失败）。
    max_consecutive_stalls: int = 3
    #: 连续多少次状态未确认后升级恢复（绝不直接判失败）。
    max_unknown_rechecks: int = 3
    #: 恢复阶梯耗尽后每次重试之间的等待，避免空转。
    recovery_pause_seconds: float = 0.25
    #: 页面无法确认时每轮确认后的等待，避免在 UNKNOWN 上空转（也绝不允许盲点）。
    unknown_pause_seconds: float = 0.5
    #: 确认到弹窗遮挡时最多定向关闭几次；之后交给恢复阶梯继续升级。
    max_popup_dismissals: int = 1
    #: 页面确认阶梯开关（QQR-5 / §3.6）：识别失败先确认，再决定是否恢复。
    confirmation: ConfirmationConfig = field(default_factory=ConfirmationConfig)

    def __post_init__(self) -> None:
        if self.max_steps < 1:
            raise ValueError("max_steps 必须 >= 1")
        if self.max_consecutive_stalls < 1:
            raise ValueError("max_consecutive_stalls 必须 >= 1")
        if self.max_unknown_rechecks < 1:
            raise ValueError("max_unknown_rechecks 必须 >= 1")
        if self.recovery_pause_seconds < 0:
            raise ValueError("recovery_pause_seconds 必须 >= 0")
        if self.unknown_pause_seconds < 0:
            raise ValueError("unknown_pause_seconds 必须 >= 0")
        if self.max_popup_dismissals < 1:
            raise ValueError("max_popup_dismissals 必须 >= 1")


class RunPhase(str, Enum):
    """契约阶段。"""

    START = "START"
    READY = "READY"
    RUNNING = "RUNNING"


_PHASE_RUN_STATE = {
    RunPhase.START: RunState.STARTING,
    RunPhase.READY: RunState.PREPARING,
    RunPhase.RUNNING: RunState.RUNNING,
}


class TaskRunner:
    """按契约执行一个任务。"""

    def __init__(
        self,
        definition: TaskDefinition,
        clock: Clock,
        token: Optional[CancellationToken] = None,
        config: Optional[RunnerConfig] = None,
    ) -> None:
        self._definition = definition
        self._contract = definition.contract
        self._observer = definition.observer
        self._adapter = definition.adapter
        self._recovery = definition.recovery
        self._captcha_guard = definition.captcha_guard
        self._recognizer = definition.state_recognizer
        self._clock = clock
        self._token = token or CancellationToken()
        self._config = config or RunnerConfig()
        # QQR-5：识别不到目标时先做多特征页面确认，再由本循环决定是否恢复。
        # 任务定义可注入自定义确认器（便于替换/测试），否则按契约构造默认实现。
        self._confirmer = definition.confirmer or PageConfirmer(
            self._observer,
            self._recognizer,
            captcha_condition=self._contract.captcha_condition,
            config=self._config.confirmation,
        )

    @property
    def definition(self) -> TaskDefinition:
        return self._definition

    def run(self) -> TaskResult:
        context = TaskContext(
            contract=self._contract,
            clock=self._clock,
            token=self._token,
            started_at=self._clock.now(),
            run_state=RunState.IDLE,
        )
        diagnostics: List[DiagnosticEvent] = []
        self._record(
            diagnostics,
            context,
            "run.start",
            f"开始任务 {self._contract.name}",
            timeout_seconds=self._contract.timeout.seconds,
        )
        try:
            return self._run(context, diagnostics)
        except Cancelled as exc:
            return self._finish(
                context,
                TaskOutcome.CANCELLED,
                f"已取消: {exc.reason}",
                diagnostics,
                RunState.CANCELLED,
            )
        except Exception as exc:  # noqa: BLE001 - 未预期异常必须留下诊断并失败
            self._record(
                diagnostics,
                context,
                "run.error",
                f"未预期异常: {type(exc).__name__}: {exc}",
            )
            return self._finish(
                context,
                TaskOutcome.FAILED,
                f"未预期异常: {type(exc).__name__}: {exc}",
                diagnostics,
                RunState.FAILED,
            )

    # ------------------------------------------------------------------ 主循环

    def _run(self, context: TaskContext, diagnostics: List[DiagnosticEvent]) -> TaskResult:
        phase = RunPhase.START
        stalls = 0
        iterations = 0
        while True:
            iterations += 1
            context.run_state = _PHASE_RUN_STATE[phase]
            context.data[PHASE_KEY] = phase.value

            if self._token.is_cancelled:
                return self._finish(
                    context,
                    TaskOutcome.CANCELLED,
                    f"已取消: {self._token.reason or 'cancelled'}",
                    diagnostics,
                    RunState.CANCELLED,
                )
            if iterations > self._config.max_steps:
                return self._finish(
                    context,
                    TaskOutcome.FAILED,
                    f"达到最大循环次数 {self._config.max_steps}，可能存在死循环",
                    diagnostics,
                    RunState.FAILED,
                )
            if context.elapsed >= self._contract.timeout.seconds:
                if context.get("recovery_exhausted"):
                    return self._finish(
                        context,
                        TaskOutcome.FAILED,
                        "恢复阶梯已耗尽且独立超时仍未恢复",
                        diagnostics,
                        RunState.FAILED,
                    )
                return self._finish(
                    context,
                    TaskOutcome.TIMEOUT,
                    f"独立超时 {self._contract.timeout.seconds:g}s",
                    diagnostics,
                    RunState.TIMEOUT,
                )

            observation = self._observer.observe(context)
            decision = self._recognizer.evaluate(observation)
            previous_state = context.state
            context.update_observation(observation, decision)
            # 只有页面状态真的发生变化，才认为任务取得了新进展并重置恢复阶梯；
            # 仅「progress_condition 当前成立」不足以证明有新进展，否则会掩盖卡死。
            if (
                previous_state is not None
                and previous_state is not decision.state
                and (context.get("recovery_attempt") or context.get("recovery_exhausted"))
            ):
                context.update_data(recovery_attempt=0, recovery_exhausted=False)
                self._record(
                    diagnostics,
                    context,
                    "recovery.reset",
                    f"页面状态 {previous_state.value} → {decision.state.value}，恢复阶梯重置",
                )
            self._record(
                diagnostics,
                context,
                "page.observed",
                decision.state.value,
                confidence=round(decision.confidence, 3),
                reason=decision.reason,
                unknown=decision.needs_recheck,
            )

            # 1) 验证码优先级最高：必须先于任何推进/恢复判断。
            if self._captcha_present(context):
                terminal = self._handle_captcha(context, diagnostics)
                if terminal is not None:
                    return terminal
                continue

            # 2) 状态未确认：先按 QQR-5 的确认阶梯「重新截图 → 重新判断 →
            #    模板 B / OCR / 页面特征 → 查弹窗 → 查验证码 → 刷新状态」，
            #    确认失败只允许恢复，绝不在 UNKNOWN 上盲点，也绝不判失败。
            if decision.needs_recheck:
                streak = int(context.get("unknown_streak", 0)) + 1
                context.update_data(unknown_streak=streak)
                self._record(
                    diagnostics,
                    context,
                    "page.unknown",
                    f"第 {streak} 次未确认页面状态；先做页面确认，不判失败",
                )
                # QQR-5：识别失败必须留下「尝试了哪些特征、各自结果」。
                self._record_feature_report(context, diagnostics, decision)
                confirmation = self._confirmer.confirm(
                    context, observation=observation, decision=decision
                )
                diagnostics.extend(confirmation.diagnostics())
                if confirmation.captcha_detected:
                    terminal = self._handle_captcha(context, diagnostics)
                    if terminal is not None:
                        return terminal
                    continue
                if confirmation.confirmed:
                    # 确认本身发现页面可识别了，等价于「状态变化 → 阶梯重置」。
                    if (
                        decision.state is not confirmation.state
                        and (
                            context.get("recovery_attempt")
                            or context.get("recovery_exhausted")
                        )
                    ):
                        context.update_data(recovery_attempt=0, recovery_exhausted=False)
                        self._record(
                            diagnostics,
                            context,
                            "recovery.reset",
                            f"页面确认 {decision.state.value} → "
                            f"{confirmation.state.value}，恢复阶梯重置",
                        )
                    context.update_data(unknown_streak=0, popup_dismissals=0)
                    self._record(
                        diagnostics,
                        context,
                        "page.confirmed",
                        f"页面确认成功: {context.state.value}（{confirmation.reason}）",
                        confidence=round(confirmation.confidence, 3),
                    )
                    # 用刚确认的状态继续走契约阶段判断；不点击、不跳过阶段。
                else:
                    if confirmation.popup_detected:
                        dismissals = int(context.get("popup_dismissals", 0)) + 1
                        context.update_data(popup_dismissals=dismissals)
                        if dismissals <= self._config.max_popup_dismissals:
                            # 弹窗遮挡：优先定向关闭，不占用恢复阶梯。
                            self._recover(
                                context,
                                diagnostics,
                                "popup_blocking",
                                action=RecoveryAction.DISMISS_POPUP,
                            )
                        else:
                            # 弹窗反复出现：交给恢复阶梯继续升级（返回 / 重进 / 重启）。
                            self._recover(context, diagnostics, "popup_blocking")
                    elif streak >= self._config.max_unknown_rechecks:
                        context.update_data(unknown_streak=0)
                        self._recover(context, diagnostics, "state_unknown")
                    self._pause_unknown()
                    continue
            elif context.get("unknown_streak"):
                context.update_data(unknown_streak=0)

            # 3) 致命错误。
            fatal = self._match_fatal(context)
            if fatal is not None:
                rule, result = fatal
                self._record(
                    diagnostics, context, "error.fatal", f"{rule.name}: {result.reason}"
                )
                return self._finish(
                    context,
                    TaskOutcome.FAILED,
                    f"致命错误 {rule.name}: {result.reason}",
                    diagnostics,
                    RunState.FAILED,
                )

            # 4) 可恢复错误。
            recoverable = self._match_recoverable(context)
            if recoverable is not None:
                rule, result = recoverable
                self._record(
                    diagnostics,
                    context,
                    "error.recoverable",
                    f"{rule.name}: {result.reason}",
                )
                self._recover(context, diagnostics, rule.name)
                continue

            # 5) 契约阶段推进。
            if phase is RunPhase.START:
                result = self._contract.start_condition.evaluate(context)
                if result.satisfied:
                    phase = RunPhase.READY
                    self._record(
                        diagnostics,
                        context,
                        "phase.ready",
                        f"start_condition 满足: {result.reason}",
                    )
                    continue
                self._record(diagnostics, context, "phase.start", result.reason)
            elif phase is RunPhase.READY:
                result = self._contract.ready_condition.evaluate(context)
                if result.satisfied:
                    phase = RunPhase.RUNNING
                    self._record(
                        diagnostics,
                        context,
                        "phase.running",
                        f"ready_condition 满足: {result.reason}",
                    )
                    continue
                self._record(diagnostics, context, "phase.prepare", result.reason)
            else:
                success = self._contract.success_condition.evaluate(context)
                if success.satisfied:
                    self._record(diagnostics, context, "task.success", success.reason)
                    return self._finish(
                        context,
                        TaskOutcome.SUCCESS,
                        success.reason,
                        diagnostics,
                        RunState.SUCCEEDED,
                    )
                progress = self._contract.progress_condition.evaluate(context)
                if progress.satisfied:
                    stalls = 0
                else:
                    stalls += 1
                    self._record(
                        diagnostics,
                        context,
                        "progress.stall",
                        f"第 {stalls} 次未满足 progress_condition: {progress.reason}",
                    )
                    if stalls >= self._config.max_consecutive_stalls:
                        stalls = 0
                        self._recover(context, diagnostics, "progress_stall")
                        continue

            # 6) 领域推进（点击 / 等待 / 滑动等）。
            step = self._adapter.advance(context)
            context.step += 1
            if step.data_updates:
                context.data.update(step.data_updates)
            self._record(
                diagnostics,
                context,
                "step.advance",
                step.description,
                actions=list(step.actions),
                progress=step.progress,
            )

    # ------------------------------------------------------------ 验证码处理

    def _captcha_present(self, context: TaskContext) -> bool:
        if context.decision is not None and context.decision.state is PageState.CAPTCHA:
            return True
        return self._contract.captcha_condition.evaluate(context).satisfied

    def _handle_captcha(
        self, context: TaskContext, diagnostics: List[DiagnosticEvent]
    ) -> Optional[TaskResult]:
        """处理验证码；返回终止结果，或 ``None`` 表示「已消失，可继续」。

        调用方在返回 ``None`` 后必须 ``continue`` 重新观测，**不得**直接推进。
        """
        context.run_state = RunState.CAPTCHA
        self._record(
            diagnostics, context, "captcha.detected", "检测到验证码，正常任务推进暂停"
        )
        outcome = self._captcha_guard.handle(context)
        self._record(
            diagnostics,
            context,
            "captcha.handled",
            outcome.detail,
            resolution=outcome.resolution.value,
            attempts=outcome.attempts,
        )
        if not outcome.solved:
            context.run_state = RunState.WAITING_FOR_HUMAN
            return self._finish(
                context,
                TaskOutcome.BLOCKED_BY_CAPTCHA,
                outcome.detail,
                diagnostics,
                RunState.WAITING_FOR_HUMAN,
            )

        # 防御性二次确认：guard 已经确认过一次，这里再抓一帧。
        observation = self._observer.observe(context)
        decision = self._recognizer.evaluate(observation)
        context.update_observation(observation, decision)
        if self._captcha_present(context):
            reentries = int(context.get("captcha_reentry", 0)) + 1
            context.update_data(captcha_reentry=reentries)
            self._record(
                diagnostics,
                context,
                "captcha.verify_failed",
                f"求解后验证码仍然存在（第 {reentries} 次）；继续处理，绝不继续任务",
            )
            if reentries >= 2:
                context.run_state = RunState.WAITING_FOR_HUMAN
                return self._finish(
                    context,
                    TaskOutcome.BLOCKED_BY_CAPTCHA,
                    "求解后验证码仍然存在，进入等待人工",
                    diagnostics,
                    RunState.WAITING_FOR_HUMAN,
                )
            return None

        context.update_data(captcha_reentry=0)
        self._record(
            diagnostics,
            context,
            "captcha.verified_gone",
            "已确认验证码消失，恢复原任务",
        )
        return None

    # ------------------------------------------------------------ 错误匹配

    def _match_fatal(
        self, context: TaskContext
    ) -> Optional[Tuple[FatalErrorSpec, ConditionResult]]:
        for rule in self._contract.fatal_error:
            result = rule.when.evaluate(context)
            if result.satisfied:
                return rule, result
        return None

    def _match_recoverable(
        self, context: TaskContext
    ) -> Optional[Tuple[RecoverableErrorSpec, ConditionResult]]:
        for rule in self._contract.recoverable_error:
            result = rule.when.evaluate(context)
            if result.satisfied:
                return rule, result
        return None

    # ------------------------------------------------------------ 恢复

    def _recover(
        self,
        context: TaskContext,
        diagnostics: List[DiagnosticEvent],
        reason: str,
        *,
        action: Optional[RecoveryAction] = None,
    ) -> None:
        context.run_state = RunState.RECOVERING
        if action is not None:
            # 定向恢复（例如确认到弹窗遮挡）：只执行这一动作，不占用恢复阶梯。
            self._record(
                diagnostics,
                context,
                "recovery.action",
                f"执行定向恢复动作 {action.value}",
                reason=reason,
                targeted=True,
            )
            step = self._adapter.recover(action, context)
            self._record(
                diagnostics,
                context,
                "recovery.done",
                step.description,
                action=action.value,
                actions=list(step.actions),
            )
            return
        attempt = int(context.get("recovery_attempt", 0))
        if self._recovery.exhausted(attempt):
            context.update_data(recovery_exhausted=True)
            self._record(
                diagnostics,
                context,
                "recovery.exhausted",
                f"恢复阶梯已耗尽（attempt={attempt}）；保持重试直到独立超时，不直接判失败",
            )
            self._pause_after_exhausted()
            return
        action = self._recovery.next_action(attempt)
        if action is RecoveryAction.GIVE_UP:
            context.update_data(recovery_exhausted=True)
            self._record(
                diagnostics,
                context,
                "recovery.exhausted",
                "恢复策略返回 GIVE_UP；保持重试直到独立超时，不直接判失败",
            )
            self._pause_after_exhausted()
            return
        self._record(
            diagnostics,
            context,
            "recovery.action",
            f"执行恢复动作 {action.value}",
            reason=reason,
            attempt=attempt,
        )
        step = self._adapter.recover(action, context)
        context.update_data(recovery_attempt=attempt + 1)
        self._record(
            diagnostics,
            context,
            "recovery.done",
            step.description,
            action=action.value,
            actions=list(step.actions),
        )

    def _pause_after_exhausted(self) -> None:
        if self._config.recovery_pause_seconds > 0:
            self._clock.sleep(self._config.recovery_pause_seconds, self._token)

    def _pause_unknown(self) -> None:
        """无法确认页面时短暂等待，避免空转（绝不在此盲点）。"""
        if self._config.unknown_pause_seconds > 0:
            self._clock.sleep(self._config.unknown_pause_seconds, self._token)

    def _record_feature_report(
        self,
        context: TaskContext,
        diagnostics: List[DiagnosticEvent],
        decision: Optional[StateDecision],
    ) -> None:
        """QQR-5：把「尝试了哪些特征、各自结果」写进诊断。"""
        lines = feature_report(decision)
        if not lines:
            return
        self._record(
            diagnostics,
            context,
            "page.features",
            "\n".join(lines),
            features=list(lines),
        )

    # ------------------------------------------------------------ 收尾

    def _finish(
        self,
        context: TaskContext,
        outcome: TaskOutcome,
        reason: str,
        diagnostics: List[DiagnosticEvent],
        run_state: RunState,
    ) -> TaskResult:
        context.run_state = run_state
        self._record(
            diagnostics,
            context,
            "run.finish",
            f"{outcome.value}: {reason}",
            steps=context.step,
            final_state=context.state.value,
        )
        return TaskResult(
            task=self._contract.name,
            outcome=outcome,
            reason=reason,
            started_at=context.started_at,
            ended_at=self._clock.now(),
            steps=context.step,
            final_state=context.state,
            run_state=run_state,
            diagnostics=tuple(diagnostics),
        )

    def _record(
        self,
        diagnostics: List[DiagnosticEvent],
        context: TaskContext,
        kind: str,
        message: str,
        **data: object,
    ) -> None:
        diagnostics.append(
            DiagnosticEvent(
                at=self._clock.now(),
                kind=kind,
                message=message,
                data=dict(data),
            )
        )
