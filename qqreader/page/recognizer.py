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
from typing import Dict, Iterable, Optional, Tuple

from ..errors import ContractViolation, StateNotConfirmed
from .features import FeatureMatch, FeatureSpec, match_feature
from .observation import PageObservation
from .states import PageState


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
    def matched(self) -> Tuple[FeatureMatch, ...]:
        return tuple(m for m in self.matches if m.matched)

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

    def __post_init__(self) -> None:
        if self.state is PageState.UNKNOWN:
            raise ContractViolation("UNKNOWN 不能拥有状态定义；它是确认失败的结果")
        if not self.features:
            raise ContractViolation(f"{self.state.value} 至少需要一个特征")
        if self.min_matched < 1:
            raise ContractViolation("min_matched 必须 >= 1")
        if not 0.0 <= self.min_score <= 1.0:
            raise ContractViolation("min_score 必须在 0..1")

    @property
    def required_features(self) -> Tuple[FeatureSpec, ...]:
        return tuple(f for f in self.features if f.required)

    def evaluate(self, observation: PageObservation) -> StateCandidate:
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

    @property
    def is_confirmed(self) -> bool:
        return self.state is not PageState.UNKNOWN

    @property
    def needs_recheck(self) -> bool:
        """状态未确认时只能重新判断，绝不推导为任务失败。"""
        return not self.is_confirmed

    def candidate(self, state: PageState) -> Optional[StateCandidate]:
        for item in self.candidates:
            if item.state is state:
                return item
        return None

    def top_candidate(self) -> Optional[StateCandidate]:
        if not self.candidates:
            return None
        return max(self.candidates, key=lambda c: (c.score, c.matched_count))

    def require_confirmed(self) -> PageState:
        """返回已确认的状态；未确认时抛 :class:`StateNotConfirmed`。

        该 API 刻意不返回布尔值，避免调用方写出
        ``if not confirmed: return "目标不存在"`` 这类错误逻辑。
        """
        if not self.is_confirmed:
            raise StateNotConfirmed(self.reason)
        return self.state

    def diagnostics(self) -> str:
        lines = [f"state={self.state.value} confidence={self.confidence:.3f}"]
        lines.append(f"reason={self.reason}")
        for item in self.candidates:
            lines.append("  " + item.summary())
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
        candidates = tuple(
            definition.evaluate(observation) for definition in self._definitions.values()
        )
        confirmed = [c for c in candidates if c.confirmed]
        if not confirmed:
            top = max(candidates, key=lambda c: (c.score, c.matched_count))
            return StateDecision(
                state=PageState.UNKNOWN,
                confidence=top.score,
                candidates=candidates,
                observation=observation,
                reason=(
                    "没有任何状态达到确认阈值；结果只能是 UNKNOWN / 重新判断，"
                    "不得推导为「目标不存在」或「任务失败」"
                ),
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
        )
