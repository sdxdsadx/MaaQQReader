"""QQR-6：广告与游戏多特征识别策略。

锁定 AGENTS.md §3.2 / §3.6 的验收点：

* 模板 A（主特征）失效但页面确实存在时，按降级链用模板 B / OCR / 页面
  结构确认状态；
* 误判为 UNKNOWN 时日志能说明每个特征（含降级链每一步）的结果；
* 区分「页面确实不在」（NOT_PRESENT）与「特征临时不匹配」
  （TEMPORARY_MISMATCH），但两者都只能重新判断，不得判任务失败。
"""

from __future__ import annotations

from qqreader.contract.conditions import Always, feature, state_in
from qqreader.contract.outcome import TaskOutcome
from qqreader.page.feature_keys import DEFAULT_FEATURE_KEYS
from qqreader.page.features import FeatureKind, FeatureSpec
from qqreader.page.observation import PageObservation
from qqreader.page.recognizer import RecognitionVerdict
from qqreader.page.states import Orientation, PageState
from qqreader.runner.confirmation import feature_report
from qqreader.runner.runner import TaskRunner
from tests.helpers import (
    QQ,
    FakeAdapter,
    FakeClock,
    QueueObserver,
    ad_playing_observation,
    home_observation,
    make_contract,
    make_definition,
    make_recognizer,
    reward_observation,
)


def _feature_match(candidate, key: str):  # noqa: ANN001, ANN201
    return next(match for match in candidate.matches if match.spec.key == key)


def test_template_a_failure_falls_back_to_ocr_and_confirms_home() -> None:
    """主页模板 A（「我的」图标）失效，但书架 OCR 仍能确认 HOME。"""
    keys = DEFAULT_FEATURE_KEYS
    observation = home_observation(icons={})
    decision = make_recognizer().evaluate(observation)

    assert decision.state is PageState.HOME
    assert decision.verdict is RecognitionVerdict.CONFIRMED
    candidate = decision.candidate(PageState.HOME)
    assert candidate is not None and candidate.confirmed

    identity = _feature_match(candidate, keys.home_nav_my)
    assert identity.fallback_used is True
    assert identity.attempts[0].matched is False  # 模板 A 失败
    assert identity.attempts[1].matched is True   # OCR 降级命中
    assert identity.matched_spec is not None
    assert identity.matched_spec.kind is FeatureKind.OCR


def test_template_a_failure_falls_back_to_structure_and_confirms_ad_playing() -> None:
    """广告播放页主 OCR 失效，但视频区域结构特征仍能确认 AD_PLAYING。"""
    keys = DEFAULT_FEATURE_KEYS
    observation = ad_playing_observation(
        ocr_texts=(),
        icons={},
        structure={"ad.video_surface": 0.9},
    )
    decision = make_recognizer().evaluate(observation)

    assert decision.state is PageState.AD_PLAYING
    assert decision.verdict is RecognitionVerdict.CONFIRMED
    candidate = decision.candidate(PageState.AD_PLAYING)
    assert candidate is not None and candidate.confirmed

    identity = _feature_match(candidate, keys.ad_ocr_countdown)
    assert identity.fallback_used is True
    assert identity.attempts[0].matched is False  # 主 OCR 失败
    assert identity.attempts[1].matched is False  # 模板 B 也失败
    assert identity.attempts[2].matched is True   # 页面结构降级命中
    assert identity.matched_spec is not None
    assert identity.matched_spec.kind is FeatureKind.STRUCTURE


def test_unknown_distinguishes_not_present_from_temporary_mismatch() -> None:
    """没有任何目标证据 → NOT_PRESENT；有局部证据但未达阈值 → TEMPORARY_MISMATCH。"""
    recognizer = make_recognizer()

    absent = recognizer.evaluate(PageObservation.empty())
    assert absent.state is PageState.UNKNOWN
    assert absent.needs_recheck is True
    assert absent.verdict is RecognitionVerdict.NOT_PRESENT
    assert absent.not_present is True
    assert absent.temporary_mismatch is False

    partial = recognizer.evaluate(
        PageObservation(
            current_app=QQ,
            orientation=Orientation.PORTRAIT,
            icons={"reward.header": 0.3},
        )
    )
    assert partial.state is PageState.UNKNOWN
    assert partial.needs_recheck is True
    assert partial.verdict is RecognitionVerdict.TEMPORARY_MISMATCH
    assert partial.temporary_mismatch is True
    assert partial.not_present is False
    # 两种 UNKNOWN 都不允许被解释成任务失败。
    assert "不得推导" in partial.reason


def test_feature_report_lists_each_failed_feature_and_fallback_attempts() -> None:
    """UNKNOWN 日志必须能回答「哪些特征失败、分数/阈值/降级链结果」。"""
    decision = make_recognizer().evaluate(
        PageObservation(
            current_app=QQ,
            orientation=Orientation.PORTRAIT,
            icons={"reward.header": 0.3},
        )
    )
    lines = feature_report(decision)
    assert lines
    joined = "\n".join(lines)

    # 兼容 QQR-5 既有断言：保留「缺失必需=」和「score=」。
    assert "缺失必需=" in joined
    assert "score=" in joined
    # QQR-6：具体失败特征、阈值与降级链每一次尝试都要可见。
    assert "reward.header" in joined
    assert "阈值" in joined
    assert "未命中" in joined


def test_fallback_confirmation_does_not_cause_early_task_failure() -> None:
    """模板 A 失效但页面存在时，调度核心按确认结果继续，而不是判失败。"""
    keys = DEFAULT_FEATURE_KEYS
    contract = make_contract(
        name="qqr6_fallback",
        start_condition=state_in(PageState.HOME, PageState.REWARD_HOME),
        ready_condition=state_in(PageState.REWARD_HOME),
        progress_condition=Always(),
        success_condition=feature(FeatureSpec(kind=FeatureKind.OCR, key="12/12")),
        timeout_seconds=10.0,
    )
    observer = QueueObserver(
        [
            home_observation(icons={}),  # 模板 A 失效，靠 OCR 降级确认 HOME
            reward_observation(ocr=("12/12",)),
        ]
    )
    adapter = FakeAdapter()
    result = TaskRunner(
        make_definition(contract, observer, adapter), FakeClock()
    ).run()

    assert result.outcome is TaskOutcome.SUCCESS
    assert result.outcome is not TaskOutcome.FAILED
    assert result.final_state is PageState.REWARD_HOME
