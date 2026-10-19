"""21:00/21:38 正式串行失败的真实 OCR 回放。"""
import json
from pathlib import Path

import pytest

from qqreader.tasks.ad import _locate_visible_corner_close
from tests.helpers import SimulatedDevice
from tests.test_ad_failures_20261004 import ad_client
from tests.test_qqr31_live_ad import _adapter, _context
from tests.test_qqr54_level_ad_retention import first_match, level_pipeline, node_hits

FRAMES = json.loads((Path(__file__).parent / 'fixtures' / 'ad_level_latest_20261004.json').read_text(encoding='utf-8'))


def frame(name):
    return [(text, tuple(box)) for text, box in FRAMES[name]['boxes']]


@pytest.mark.parametrize('pending', [False, True])
def test_browse_retention_exits_instead_of_launching_third_party(pending):
    device = SimulatedDevice()
    adapter = _adapter(device)
    context = _context(ocr_texts=tuple(t for t, _ in frame('browse_retention')))
    if pending:
        context.update_data(ad_exit_sent_at=context.now - 5)
    adapter.advance(context)
    assert device.calls == [('tap_feature', 'ad_ocr_force_exit')]


def test_stalled_acceleration_uses_actual_top_skip():
    boxes = frame('browse_acceleration')
    action = _locate_visible_corner_close(ad_client(boxes))
    assert action is not None
    assert (action.x, action.y) == (576, 29)
    device = SimulatedDevice()
    adapter = _adapter(device)
    adapter._navigation_client = ad_client(boxes)
    context = _context(ocr_texts=tuple(t for t, _ in boxes), ad_exit_sent_at=-21)
    adapter.advance(context)
    assert device.calls == [('tap_point', 576, 29)]


@pytest.mark.parametrize('current', ['AdConfirmSkipBrowse', 'LevelAdUnknownWait'])
def test_actual_level_top_return_is_recognized_then_checks_points(current):
    data = level_pipeline()
    boxes = frame('level_top_return')
    node, _ = first_match(data, current, boxes)
    assert node == 'AdReturnedAfterClose'
    assert node_hits(data['AdReturnStable'], boxes) is not None
    node, _ = first_match(data, 'AdReturnStable', boxes,
                          anchors=dict(data['LevelClickPointsAd']['anchor']))
    assert node == 'LevelAfterPointsAd'
    node, _ = first_match(data, node, boxes,
                          hits={'LevelClickPointsAdAgain': 2})
    assert node == 'LevelVerifyPointsScroll'
    # 任务行在顶部以下：向下寻找内容，而非反复向顶部滑动。
    assert data[node]['begin'][1] > data[node]['end'][1]
    assert node_hits(data['LevelPointsSectionFound'], boxes) is None


def test_new_level_return_captcha_still_precedes_background():
    from tests.test_daily_popups import frame as popup_frame
    boxes = frame('level_top_return') + popup_frame('reward_captcha_with_x')
    node, _ = first_match(level_pipeline(), 'LevelAdUnknownWait', boxes)
    assert node == 'AdSlideCaptchaDetected'


def test_coin_source_return_from_new_top_continues_points_search():
    data = level_pipeline()
    boxes = frame('level_top_return')
    node, _ = first_match(data, 'AdReturnStable', boxes,
                          anchors=dict(data['LevelClickCoinAd']['anchor']))
    assert node == 'LevelAfterCoinAd'


def test_fresh_captcha_does_not_click_browse_skip():
    from tests.test_daily_popups import frame as popup_frame
    action = _locate_visible_corner_close(ad_client(frame('browse_acceleration') + popup_frame('reward_captcha_with_x')))
    assert action.kind.value == 'WAIT'


@pytest.mark.parametrize('current', ['LevelAfterPointsAd', 'LevelVerifyPointsScroll', 'LevelAfterCoinAd'])
def test_captcha_on_next_frame_blocks_level_verification_swipes(current):
    from tests.test_daily_popups import frame as popup_frame
    boxes = frame('level_top_return') + popup_frame('reward_captcha_with_x')
    node, _ = first_match(level_pipeline(), current, boxes,
                          hits={'LevelClickPointsAdAgain': 2})
    assert node == 'AdSlideCaptchaDetected'
