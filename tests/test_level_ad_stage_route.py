"""积分广告已退出后的真实等级页仍含积分标题，不能误接赠币分支。"""
import json
from pathlib import Path

import pytest

from tests.test_qqr54_level_ad_retention import first_match, level_pipeline

FRAMES = json.loads((Path(__file__).parent / 'fixtures' / 'level_stage_return_20261004.json').read_text(encoding='utf-8'))


def frame(name):
    return [(text, tuple(box)) for text, box in FRAMES[name]['boxes']]


@pytest.mark.parametrize('current', ['LevelClickPointsAd', 'LevelClickPointsAdAgain'])
def test_points_ad_return_routes_to_points_verification_and_bounded_retry(current):
    data = level_pipeline()
    # 采用实际成功点击节点声明的运行期锚点，含重试入口。
    anchors = dict(data[current]['anchor'])
    node, _ = first_match(data, 'AdReturnStable', frame('points_return'), anchors=anchors)
    assert node == 'LevelAfterPointsAd'
    node, box = first_match(data, node, frame('points_return'), anchors=anchors)
    assert node == 'LevelClickPointsAdAgain'
    assert box == (577, 589, 86, 29)
    node, _ = first_match(data, 'LevelAfterPointsAd', frame('points_return'),
                          hits={'LevelClickPointsAdAgain': 2}, anchors=anchors)
    assert node == 'LevelVerifyPointsScroll'


def test_coin_ad_return_preserves_coin_then_points_order():
    data = level_pipeline()
    anchors = dict(data['LevelClickCoinAd']['anchor'])
    node, _ = first_match(data, 'AdReturnStable', frame('points_return'), anchors=anchors)
    assert node == 'LevelAfterCoinAd'


def test_return_without_ad_source_does_not_guess_coin_or_points():
    data = level_pipeline()
    with pytest.raises(AssertionError, match='next 无一命中'):
        first_match(data, 'AdReturnStable', frame('points_return'), anchors={})


def test_ad_source_return_does_not_override_captcha():
    from tests.test_daily_popups import frame as popup_frame
    data = level_pipeline()
    node, _ = first_match(data, 'AdReturnStable', frame('points_return') + popup_frame('reward_captcha_with_x'),
                         anchors=dict(data['LevelClickPointsAd']['anchor']))
    assert node == 'AdSlideCaptchaDetected'
