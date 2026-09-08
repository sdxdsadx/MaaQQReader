"""任务契约条件原语的组合语义。"""

from __future__ import annotations

from qqreader.contract.conditions import (
    Always,
    AnyOf,
    FeatureMatches,
    Never,
    NotCondition,
    StateIn,
    StateIs,
    all_of,
    any_of,
    feature,
    predicate,
    state_in,
)
from qqreader.page.features import FeatureKind, FeatureSpec
from qqreader.page.states import PageState
from tests.helpers import home_observation, make_context, reward_observation


def test_state_is_and_state_in() -> None:
    context = make_context(home_observation())
    assert StateIs(PageState.HOME).evaluate(context).satisfied is True
    assert StateIs(PageState.REWARD_HOME).evaluate(context).satisfied is False
    assert StateIn((PageState.HOME, PageState.REWARD_HOME)).evaluate(context).satisfied is True
    assert state_in(PageState.REWARD_HOME).evaluate(context).satisfied is False


def test_feature_matches_uses_observation() -> None:
    context = make_context(home_observation())
    spec = FeatureSpec(kind=FeatureKind.OCR, key="书架")
    result = feature(spec).evaluate(context)
    assert result.satisfied is True
    assert "书架" in result.reason


def test_all_any_not() -> None:
    context = make_context(reward_observation())
    is_reward = StateIs(PageState.REWARD_HOME)
    has_watch = feature(FeatureSpec(kind=FeatureKind.OCR, key="立即观看"))
    assert all_of(is_reward, has_watch).evaluate(context).satisfied is True
    assert any_of(StateIs(PageState.HOME), has_watch).evaluate(context).satisfied is True
    assert NotCondition(is_reward).evaluate(context).satisfied is False
    assert AnyOf((Never(), Always())).evaluate(context).satisfied is True


def test_predicate_condition() -> None:
    context = make_context(home_observation())
    condition = predicate(lambda ctx: ctx.observation.current_app == "com.qq.reader", "当前 App")
    assert condition.evaluate(context).satisfied is True
    assert "当前 App" in condition.evaluate(context).reason


def test_callable_condition_short_circuits() -> None:
    context = make_context(home_observation())
    calls = []

    def record(name, value):
        def _inner(_context):
            from qqreader.contract.conditions import ConditionResult

            calls.append(name)
            return ConditionResult(value, name)

        return _inner

    from qqreader.contract.conditions import callable_condition

    condition = all_of(
        callable_condition(record("a", False), "a"),
        callable_condition(record("b", True), "b"),
    )
    assert condition.evaluate(context).satisfied is False
    assert calls == ["a"], "AllOf 应在第一个不满足处短路"
