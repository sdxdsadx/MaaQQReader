"""页面状态机：多特征确认、UNKNOWN 语义、状态转移。"""

from __future__ import annotations

import pytest

from qqreader.errors import StateNotConfirmed
from qqreader.page.features import FeatureKind, FeatureSpec, MatchMode, match_feature
from qqreader.page.observation import PageObservation
from qqreader.page.recognizer import PageStateRecognizer, StateDefinition
from qqreader.page.states import (
    REQUIRED_PAGE_STATES,
    Orientation,
    PageState,
)
from tests.helpers import (
    QQ,
    ad_playing_observation,
    ad_result_observation,
    home_observation,
    make_recognizer,
    reward_observation,
)


def test_required_states_have_definitions() -> None:
    recognizer = make_recognizer()
    defined = {d.state for d in recognizer.definitions}
    for state in REQUIRED_PAGE_STATES:
        if state is PageState.UNKNOWN:
            assert state not in defined, "UNKNOWN 必须是确认失败的结果，不能有定义"
        else:
            assert state in defined, f"缺少状态定义: {state.value}"
    # HOME 是 §3.4 需要的额外公共起点。
    assert PageState.HOME in defined


def test_home_is_confirmed_by_multiple_features() -> None:
    decision = make_recognizer().evaluate(home_observation())
    assert decision.state is PageState.HOME
    assert decision.is_confirmed
    candidate = decision.candidate(PageState.HOME)
    assert candidate is not None
    assert candidate.matched_count >= 3


def test_single_weak_evidence_is_unknown_not_absent() -> None:
    observation = PageObservation(current_app=QQ, orientation=Orientation.PORTRAIT)
    decision = make_recognizer().evaluate(observation)
    assert decision.state is PageState.UNKNOWN
    assert decision.needs_recheck
    assert "不得推导" in decision.reason


def test_empty_observation_is_unknown() -> None:
    decision = make_recognizer().evaluate(PageObservation.empty())
    assert decision.state is PageState.UNKNOWN
    assert decision.confidence == 0.0
    assert decision.needs_recheck


def test_require_confirmed_raises_state_not_confirmed() -> None:
    decision = make_recognizer().evaluate(PageObservation.empty())
    with pytest.raises(StateNotConfirmed):
        decision.require_confirmed()


def test_required_feature_blocks_confirmation() -> None:
    # 缺少必需的「我的」图标：即使其它特征齐全，HOME 也不能确认。
    observation = home_observation(icons={})
    decision = make_recognizer().evaluate(observation)
    home = decision.candidate(PageState.HOME)
    assert home is not None
    assert home.required_ok is False
    assert home.confirmed is False
    assert decision.state is PageState.UNKNOWN


def test_regex_feature_matches() -> None:
    spec = FeatureSpec(
        kind=FeatureKind.OCR,
        key=r"看小视频.*明日再来",
        mode=MatchMode.REGEX,
    )
    match = match_feature(spec, reward_observation(ocr=("看小视频今日任务明日再来",)))
    assert match.matched is True
    assert match.score == 1.0


def test_higher_score_state_wins() -> None:
    low = StateDefinition(
        state=PageState.HOME,
        features=(
            FeatureSpec(kind=FeatureKind.OCR, key="foo"),
            FeatureSpec(kind=FeatureKind.OCR, key="bar"),
        ),
        min_score=0.3,
        min_matched=1,
    )
    high = StateDefinition(
        state=PageState.REWARD_HOME,
        features=(
            FeatureSpec(kind=FeatureKind.OCR, key="foo", weight=3.0),
            FeatureSpec(kind=FeatureKind.OCR, key="baz", weight=1.0),
        ),
        min_score=0.3,
        min_matched=1,
    )
    recognizer = PageStateRecognizer([low, high])
    decision = recognizer.evaluate(PageObservation(ocr_texts=("foo",)))
    assert decision.state is PageState.REWARD_HOME
    assert decision.candidate(PageState.HOME).confirmed is True
    assert decision.candidate(PageState.REWARD_HOME).confirmed is True


def test_page_state_transition_sequence() -> None:
    recognizer = make_recognizer()
    script = (
        home_observation(),
        reward_observation(),
        ad_playing_observation(),
        ad_result_observation(),
        reward_observation(ocr=("12/12",)),
    )
    states = [recognizer.evaluate(observation).state for observation in script]
    assert states == [
        PageState.HOME,
        PageState.REWARD_HOME,
        PageState.AD_PLAYING,
        PageState.AD_RESULT,
        PageState.REWARD_HOME,
    ]


def test_repeated_evaluation_is_stateless() -> None:
    """识别器不得把上一次状态当作隐含前提。"""
    recognizer = make_recognizer()
    assert recognizer.evaluate(home_observation()).state is PageState.HOME
    # 紧接着给一帧无法确认的观测：结果必须是 UNKNOWN，而不是沿用 HOME。
    assert recognizer.evaluate(PageObservation.empty()).state is PageState.UNKNOWN
    assert recognizer.evaluate(home_observation()).state is PageState.HOME
