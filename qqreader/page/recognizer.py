"""多特征状态确认。

设计要点（AGENTS.md §3.2）：

* 一个状态只有在「必需特征全部命中 + 命中数量达到下限 + 加权分数达到阈值」
  时才算确认。
* 没有任何状态确认时，结果只能是 ``UNKNOWN``，且 ``needs_recheck=True``；
  **不允许**把「没确认」翻译成「目标不存在」或「任务失败」。
* 识别器是无状态的：每次都用当前观测重新判断，不保留上一次状态作为隐含前提。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict, Iterable, Optional, Tuple

from ..errors import ContractViolation, StateNotConfirmed
from .features import FeatureKind, FeatureMatch, FeatureSpec, match_feature
from .observation import PageObservation
from .states import PageState


class RecognitionVerdict(str, Enum):
    """多特征识别结论。

    ``UNKNOWN`` 仍然只表示「未确认」；这里进一步区分：

    * ``CONFIRMED``：达到确认阈值；
    * ``TEMPORARY_MISMATCH``：页面上存在部分相关证据（模板分数偏低、部分
      OCR/结构命中），但还不足以确认——只能重新判断/恢复；
    * ``NOT_PRESENT``：所有目标特征都没有任何证据，倾向于「当前页面确实
      不是目标页面」，但这**不是**任务失败，仍然只能重新判断/恢复。
    """

    CONFIRMED = "CONFIRMED"
    TEMPORARY_MISMATCH = "TEMPORARY_MISMATCH"
    NOT_PRESENT = "NOT_PRESENT"


@dataclass(frozen=True)
class StateCandidate:
    """某个状态定义针对一次观测的评估结果。"""

    state: PageState
    score: float
    matched_count: int
    total_count: int
    matches: Tuple[FeatureMatch, ...]
    required_ok: bool
    confirmed: bool

    @property
    def missing_required(self) -> Tuple[FeatureMatch, ...]:
        return tuple(m for m in self.matches if m.spec.required and not m.matched)

    @property
    def failed(self) -> Tuple[FeatureMatch, ...]:
        """全部未命中的特征（不限于 required），用于日志说明哪些特征失败。"""
        return tuple(m for m in self.matches if not m.matched)

    @property
    def matched(self) -> Tuple[FeatureMatch, ...]:
        return tuple(m for m in self.matches if m.matched)

    @property
    def fallback_matched(self) -> Tuple[FeatureMatch, ...]:
        return tuple(m for m in self.matches if m.fallback_used)

    @property
    def evidence_present(self) -> bool:
        """是否存在目标页面的局部证据（排除 App / 方向这类背景特征）。

        用于区分「页面确实不在」（没有任何目标证据）与「特征临时不匹配」
        （有目标证据但分数/组合不足）。无论哪种，调用方都只能重新判断，
        不得推导为任务失败。
        """
        for match in self.matches:
            if match.spec.kind in (FeatureKind.CURRENT_APP, FeatureKind.ORIENTATION):
                continue
            if match.matched:
                return True
            if any(attempt.score > 0.0 for attempt in match.attempts):
                return True
        return False

    def summary(self) -> str:
        return (
            f"{self.state.value}: score={self.score:.3f} "
            f"matched={self.matched_count}/{self.total_count} "
            f"required_ok={self.required_ok} confirmed={self.confirmed}"
        )


@dataclass(frozen=True)
class StateDefinition:
    """一个页面状态的多特征定义。"""

    state: PageState
    features: Tuple[FeatureSpec, ...]
    min_score: float = 0.4
    min_matched: int = 2
    description: str = ""
    #: issue #12：排除词（负向锚点）。观测 OCR 中任一排除词出现时，本状态
    #: 一律不确认。用于挡住「弱特征组合」在错误页面上凑分误判——例如
    #: 游戏中心列表页自带「领币」入口文案 + 竖屏即可凑满 GAME_RUNNING 的
    #: 确认阈值（真机 2026-09-13 score=0.605），让任务在列表页空转至超时。
    excluded_texts: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.state is PageState.UNKNOWN:
            raise ContractViolation("UNKNOWN 不能拥有状态定义；它是确认失败的结果")
        if not self.features:
            raise ContractViolation(f"{self.state.value} 至少需要一个特征")
        if self.min_matched < 1:
            raise ContractViolation("min_matched 必须 >= 1")
        if not 0.0 <= self.min_score <= 1.0:
            raise ContractViolation("min_score 必须在 0..1")
        for marker in self.excluded_texts:
            if not isinstance(marker, str) or not marker.strip():
                raise ContractViolation("excluded_texts 必须是非空字符串")

    def has_excluded_text(self, observation: PageObservation) -> bool:
        """观测 OCR 是否命中任一排除词（负向锚点）。"""
        if not self.excluded_texts:
            return False
        for text in observation.ocr_texts:
            if not text or not text.strip():
                continue
            for marker in self.excluded_texts:
                if marker in text:
                    return True
        return False

    @property
    def required_features(self) -> Tuple[FeatureSpec, ...]:
        return tuple(f for f in self.features if f.required)

    def evaluate(self, observation: PageObservation) -> StateCandidate:
        # issue #12：排除词命中时直接按零证据处理，不进入正常打分。
        # 部分命中（如 0.6 分）不足以确认，但会污染 UNKNOWN 时的 top 候选
        # 排序与 confidence，并把 TEMPORARY_MISMATCH 伪装成「目标页局部证据」。
        if self.has_excluded_text(observation):
            matches = tuple(
                FeatureMatch(spec=spec, matched=False, score=0.0, detail="排除词命中，本状态不参与确认")
                for spec in self.features
            )
            return StateCandidate(
                state=self.state,
                score=0.0,
                matched_count=0,
                total_count=len(matches),
                matches=matches,
                required_ok=False,
                confirmed=False,
            )
        matches = tuple(match_feature(spec, observation) for spec in self.features)
        total_weight = sum(m.spec.weight for m in matches)
        score = (
            sum(m.score * m.spec.weight for m in matches) / total_weight
            if total_weight > 0
            else 0.0
        )
        matched_count = sum(1 for m in matches if m.matched)
        required_ok = all(m.matched for m in matches if m.spec.required)
        confirmed = (
            required_ok
            and matched_count >= self.min_matched
            and score >= self.min_score
        )
        return StateCandidate(
            state=self.state,
            score=score,
            matched_count=matched_count,
            total_count=len(matches),
            matches=matches,
            required_ok=required_ok,
            confirmed=confirmed,
        )


@dataclass(frozen=True)
class StateDecision:
    """一次状态判断的结论。"""

    state: PageState
    confidence: float
    candidates: Tuple[StateCandidate, ...]
    observation: PageObservation
    reason: str
    verdict: RecognitionVerdict = RecognitionVerdict.NOT_PRESENT

    @property
    def is_confirmed(self) -> bool:
        return self.state is not PageState.UNKNOWN

    @property
    def needs_recheck(self) -> bool:
        """状态未确认时只能重新判断，绝不推导为任务失败。"""
        return not self.is_confirmed

    @property
    def temporary_mismatch(self) -> bool:
        return self.verdict is RecognitionVerdict.TEMPORARY_MISMATCH

    @property
    def not_present(self) -> bool:
        return self.verdict is RecognitionVerdict.NOT_PRESENT

    def candidate(self, state: PageState) -> Optional[StateCandidate]:
        for item in self.candidates:
            if item.state is state:
                return item
        return None

    def top_candidate(self) -> Optional[StateCandidate]:
        if not self.candidates:
            return None
        # 先看是否已有目标局部证据，再看分数/命中数；这样 UNKNOWN 时排障
        # 日志会指向「最像目标但还没确认」的状态，而不是只有 App/方向的背景状态。
        return max(
            self.candidates,
            key=lambda c: (c.evidence_present, c.score, c.matched_count),
        )

    @property
    def failed_features(self) -> Tuple[str, ...]:
        """最高分候选上未命中的特征描述（含降级链尝试结果）。"""
        top = self.top_candidate()
        if top is None:
            return ()
        return tuple(match.render() for match in top.failed)

    def require_confirmed(self) -> PageState:
        """返回已确认的状态；未确认时抛 :class:`StateNotConfirmed`。

        该 API 刻意不返回布尔值，避免调用方写出
        ``if not confirmed: return "目标不存在"`` 这类错误逻辑。
        """
        if not self.is_confirmed:
            raise StateNotConfirmed(self.reason)
        return self.state

    def diagnostics(self) -> str:
        lines = [
            f"state={self.state.value} confidence={self.confidence:.3f} "
            f"verdict={self.verdict.value}"
        ]
        lines.append(f"reason={self.reason}")
        for item in self.candidates:
            lines.append("  " + item.summary())
            for match in item.failed:
                lines.append("    " + match.render())
        return "\n".join(lines)


class PageStateRecognizer:
    """按一组状态定义，把观测映射到页面状态。"""

    def __init__(self, definitions: Iterable[StateDefinition]) -> None:
        self._definitions: Dict[PageState, StateDefinition] = {}
        for definition in definitions:
            if definition.state in self._definitions:
                raise ContractViolation(f"状态定义重复: {definition.state.value}")
            self._definitions[definition.state] = definition
        if not self._definitions:
            raise ContractViolation("至少需要一个状态定义")

    @property
    def definitions(self) -> Tuple[StateDefinition, ...]:
        return tuple(self._definitions.values())

    def definition(self, state: PageState) -> StateDefinition:
        try:
            return self._definitions[state]
        except KeyError as exc:  # pragma: no cover - 开发期错误
            raise ContractViolation(f"没有 {state.value} 的状态定义") from exc

    def evaluate(self, observation: PageObservation) -> StateDecision:
        # issue #12：带排除词的状态先剔除——排除词命中说明当前页面必然不是
        # 该状态（如游戏中心列表页不是 GAME_RUNNING），即使其它特征凑分达标。
        candidates = tuple(
            definition.evaluate(observation)
            for definition in self._definitions.values()
            if not definition.has_excluded_text(observation)
        )
        confirmed = [c for c in candidates if c.confirmed]
        if not confirmed:
            top = max(
                candidates,
                key=lambda c: (c.evidence_present, c.score, c.matched_count),
            )
            verdict = (
                RecognitionVerdict.TEMPORARY_MISMATCH
                if top.evidence_present
                else RecognitionVerdict.NOT_PRESENT
            )
            if verdict is RecognitionVerdict.TEMPORARY_MISMATCH:
                reason = (
                    f"未达到确认阈值，但检测到 {top.state.value} 的局部证据"
                    "（特征临时不匹配）；结果只能是 UNKNOWN / 重新判断，"
                    "不得推导为「目标不存在」或「任务失败」"
                )
            else:
                reason = (
                    f"所有状态均无目标特征证据（{top.state.value} 最接近）；"
                    "结果只能是 UNKNOWN / 重新判断，不得推导为「目标不存在」"
                    "或「任务失败」"
                )
            return StateDecision(
                state=PageState.UNKNOWN,
                confidence=top.score,
                candidates=candidates,
                observation=observation,
                reason=reason,
                verdict=verdict,
            )
        # 分数优先、命中数其次；并列时保持定义顺序，保证可复现。
        confirmed.sort(key=lambda c: (c.score, c.matched_count), reverse=True)
        best = confirmed[0]
        return StateDecision(
            state=best.state,
            confidence=best.score,
            candidates=candidates,
            observation=observation,
            reason=(
                f"{best.state.value} 已确认（score={best.score:.3f}，"
                f"命中 {best.matched_count}/{best.total_count}）"
            ),
            verdict=RecognitionVerdict.CONFIRMED,
        )
