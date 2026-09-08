"""任务契约的条件原语。

契约的 8 个字段都是「条件」，本模块提供可组合、可测试、无副作用的条件
对象。条件只**判断**当前上下文，不执行点击、不修改状态；副作用属于
:class:`~qqreader.runtime.context.TaskAdapter`。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable, FrozenSet, Mapping, Optional, Tuple

from ..page.feature_keys import DEFAULT_FEATURE_KEYS, FeatureKeys
from ..page.features import FeatureKind, FeatureSpec, MatchMode, match_feature
from ..page.states import PageState

if TYPE_CHECKING:  # pragma: no cover - 仅用于类型标注，避免运行期循环导入
    from ..runtime.context import TaskContext


@dataclass(frozen=True)
class ConditionResult:
    """条件判断结果。"""

    satisfied: bool
    reason: str
    evidence: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def yes(cls, reason: str = "满足", **evidence: Any) -> "ConditionResult":
        return cls(True, reason, dict(evidence))

    @classmethod
    def no(cls, reason: str = "不满足", **evidence: Any) -> "ConditionResult":
        return cls(False, reason, dict(evidence))


class Condition:
    """条件协议。

    自定义条件只需实现 :meth:`evaluate` 与 :meth:`describe`。
    """

    def evaluate(self, context: "TaskContext") -> ConditionResult:  # pragma: no cover
        raise NotImplementedError

    def describe(self) -> str:  # pragma: no cover
        return type(self).__name__


@dataclass(frozen=True)
class Always(Condition):
    def evaluate(self, context: "TaskContext") -> ConditionResult:
        return ConditionResult.yes("恒真")

    def describe(self) -> str:
        return "always"


@dataclass(frozen=True)
class Never(Condition):
    def evaluate(self, context: "TaskContext") -> ConditionResult:
        return ConditionResult.no("恒假")

    def describe(self) -> str:
        return "never"


@dataclass(frozen=True)
class CallableCondition(Condition):
    """用普通函数包装的条件（便于测试与快速原型）。"""

    fn: Callable[["TaskContext"], ConditionResult]
    description: str = "callable"

    def evaluate(self, context: "TaskContext") -> ConditionResult:
        return self.fn(context)

    def describe(self) -> str:
        return self.description


@dataclass(frozen=True)
class StateIs(Condition):
    """当前已确认的页面状态恰好是某个状态。"""

    state: PageState

    def evaluate(self, context: "TaskContext") -> ConditionResult:
        actual = context.decision.state
        return ConditionResult(
            actual is self.state,
            f"state={actual.value}，期望 {self.state.value}",
            {"state": actual.value, "expected": self.state.value},
        )

    def describe(self) -> str:
        return f"state == {self.state.value}"


@dataclass(frozen=True)
class StateIn(Condition):
    """当前已确认的页面状态属于某个集合。"""

    states: FrozenSet[PageState]

    def __post_init__(self) -> None:
        # 允许传入任意可迭代对象（元组/列表），统一归一化为 frozenset。
        object.__setattr__(self, "states", frozenset(self.states))

    def evaluate(self, context: "TaskContext") -> ConditionResult:
        actual = context.decision.state
        expected = sorted(s.value for s in self.states)
        return ConditionResult(
            actual in self.states,
            f"state={actual.value}，期望属于 {expected}",
            {"state": actual.value, "expected": expected},
        )

    def describe(self) -> str:
        return "state in {" + ", ".join(sorted(s.value for s in self.states)) + "}"


@dataclass(frozen=True)
class FeatureMatches(Condition):
    """某条页面特征在最近一次观测中命中。"""

    spec: FeatureSpec

    def evaluate(self, context: "TaskContext") -> ConditionResult:
        result = match_feature(self.spec, context.observation)
        return ConditionResult(
            result.matched,
            result.detail,
            {"score": result.score, "kind": self.spec.kind.value},
        )

    def describe(self) -> str:
        return f"feature[{self.spec.kind.value}:{self.spec.key}]"


@dataclass(frozen=True)
class AllOf(Condition):
    conditions: Tuple[Condition, ...]

    def evaluate(self, context: "TaskContext") -> ConditionResult:
        evidence = {}
        for condition in self.conditions:
            result = condition.evaluate(context)
            evidence[condition.describe()] = result.satisfied
            if not result.satisfied:
                return ConditionResult(False, f"任一不满足: {result.reason}", evidence)
        return ConditionResult(True, "全部满足", evidence)

    def describe(self) -> str:
        return "all(" + ", ".join(c.describe() for c in self.conditions) + ")"


@dataclass(frozen=True)
class AnyOf(Condition):
    conditions: Tuple[Condition, ...]

    def evaluate(self, context: "TaskContext") -> ConditionResult:
        evidence = {}
        reasons = []
        for condition in self.conditions:
            result = condition.evaluate(context)
            evidence[condition.describe()] = result.satisfied
            reasons.append(result.reason)
            if result.satisfied:
                return ConditionResult(True, f"任一满足: {result.reason}", evidence)
        return ConditionResult(False, "全部不满足: " + "; ".join(reasons), evidence)

    def describe(self) -> str:
        return "any(" + ", ".join(c.describe() for c in self.conditions) + ")"


@dataclass(frozen=True)
class NotCondition(Condition):
    condition: Condition

    def evaluate(self, context: "TaskContext") -> ConditionResult:
        result = self.condition.evaluate(context)
        return ConditionResult(not result.satisfied, f"取反: {result.reason}", dict(result.evidence))

    def describe(self) -> str:
        return f"not({self.condition.describe()})"


def all_of(*conditions: Condition) -> Condition:
    return AllOf(tuple(conditions))


def any_of(*conditions: Condition) -> Condition:
    return AnyOf(tuple(conditions))


def not_(condition: Condition) -> Condition:
    return NotCondition(condition)


def state_in(*states: PageState) -> Condition:
    return StateIn(tuple(states))


def feature(spec: FeatureSpec) -> Condition:
    return FeatureMatches(spec)


def callable_condition(
    fn: Callable[["TaskContext"], ConditionResult], description: str = "callable"
) -> Condition:
    return CallableCondition(fn, description)


def predicate(
    fn: Callable[["TaskContext"], bool], description: str = "predicate"
) -> Condition:
    """把布尔函数包装成条件（满足时 reason 为函数名/描述）。"""

    def _evaluate(context: "TaskContext") -> ConditionResult:
        ok = bool(fn(context))
        return ConditionResult(ok, f"{description}: {'满足' if ok else '不满足'}")

    return CallableCondition(_evaluate, description)


def build_popup_condition(keys: FeatureKeys = DEFAULT_FEATURE_KEYS) -> Condition:
    """默认「普通弹窗遮挡」条件。

    QQR-5 要求在识别不到目标时**先检查弹窗**，而不是直接判定失败。这里只用
    逻辑特征名表达，具体模板/OCR 资源由识别适配器提供（见
    :mod:`qqreader.page.feature_keys`）。
    """

    return any_of(
        feature(
            FeatureSpec(
                kind=FeatureKind.TEMPLATE,
                key=keys.popup_close,
                threshold=0.7,
                mode=MatchMode.MIN_SCORE,
                description="弹窗关闭按钮",
            )
        ),
        feature(
            FeatureSpec(
                kind=FeatureKind.OCR,
                key=keys.popup_ocr_cancel,
                mode=MatchMode.EQUALS,
                description="弹窗取消文案",
            )
        ),
    )
