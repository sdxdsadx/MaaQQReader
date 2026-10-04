"""10-04 最新每日运行失败：使用原始 Maa OCR 帧复查出口与加载恢复。"""
import copy
import json
from pathlib import Path

import pytest

from qqreader.maa import RecoResult
from qqreader.page.observation import PageObservation
from qqreader.page.states import Orientation, RunState
from qqreader.tasks.ad import _locate_visible_corner_close
from tests.helpers import SimulatedDevice, make_context, make_recognizer
from tests.test_maa_adapter import FakeMaaClient
from tests.test_qqr31_live_ad import _adapter
from tests.test_qqr54_level_ad_retention import first_match, level_pipeline

FRAMES = json.loads((Path(__file__).parent / 'fixtures' / 'ad_failures_20261004.json').read_text(encoding='utf-8'))


def frame(name):
    return [(text, tuple(box)) for text, box in FRAMES[name]['boxes']]


def ad_client(boxes):
    def recognize(kind, params, shot):
        return RecoResult('OCR', True, detail={'all': [
            {'text': text, 'box': list(box), 'score': 0.99} for text, box in boxes]})
    return FakeMaaClient(recognizer=recognize)


def test_reward_popup_uses_visible_top_right_skip_not_left_corner():
    action = _locate_visible_corner_close(ad_client(frame('ad_reward_popup')))
    assert action is not None
    assert (action.x, action.y) == (622, 27)


def test_failed_exit_fallback_rechecks_actual_reward_popup_exit():
    boxes = frame('ad_reward_popup')
    device = SimulatedDevice()
    adapter = _adapter(device)
    adapter._navigation_client = ad_client(boxes)
    obs = PageObservation(orientation=Orientation.PORTRAIT, ocr_texts=tuple(t for t, _ in boxes))
    context = make_context(obs, run_state=RunState.RUNNING)
    context.update_observation(obs, make_recognizer().evaluate(obs))
    context.update_data(ad_exit_sent_at=context.now - 21, ad_initial_wait_done=True)
    adapter.advance(context)
    assert device.calls == [('tap_point', 622, 27)]
    assert context.get('ad_exit_error') is None


def test_middle_return_continue_experience_is_never_exit_target():
    boxes = [item for item in frame('ad_reward_popup') if '跳过' not in item[0]]
    assert _locate_visible_corner_close(ad_client(boxes)) is None


def test_fresh_captcha_frame_blocks_completed_ad_exit():
    from tests.test_daily_popups import frame as popup_frame
    from qqreader.tasks.plan import ActionKind
    action = _locate_visible_corner_close(ad_client(popup_frame('reward_captcha_with_x')))
    assert action.kind is ActionKind.WAIT


@pytest.mark.parametrize('current', ['LevelClickCoinAd', 'LevelClickPointsAd', 'AdScrollDownRepeat'])
def test_level_blank_loading_waits_without_scrolling(current):
    data = level_pipeline()
    node, _ = first_match(data, current, frame('level_loading'))
    assert data[node]['action'] == 'DoNothing'
    assert node == 'LevelAdUnknownWait'


def test_level_my_page_reenters_level_without_ad_swipes():
    data = level_pipeline()
    node, _ = first_match(data, 'AdScrollDownRepeat', frame('level_my_return'))
    assert node == 'LevelAdMyPageReturn'
    node, box = first_match(data, node, frame('level_my_return'))
    assert data[node]['action'] == 'Click'
    assert box == (246, 330, 51, 34)
    node, _ = first_match(data, node, frame('level_coin_entry'))
    assert node == 'LevelPageReady'


def test_level_unknown_wait_is_bounded_without_blind_inputs():
    data = level_pipeline()
    hits = {}
    current = 'LevelClickCoinAd'
    for _ in range(20):
        current, _ = first_match(data, current, frame('level_loading'), hits)
        assert data[current]['action'] == 'DoNothing'
        hits[current] = hits.get(current, 0) + 1
    with pytest.raises(AssertionError, match='next 无一命中'):
        first_match(data, current, frame('level_loading'), hits)


def test_level_page_recovery_override_is_idempotent():
    from tests.test_qqr54_level_ad_retention import run_task
    once = level_pipeline()
    twice = copy.deepcopy(once)
    run_task._apply_level_ad_runtime_overrides(twice)
    assert once == twice


def test_level_upgrade_overlay_is_confirmed_then_cancelled_before_my_tab():
    data = level_pipeline()
    boxes = frame('level_upgrade_over_shelf')
    node, _ = first_match(data, 'LevelBackUntilHome', boxes)
    assert node == 'LevelUpgradeVisible'
    assert data[node]['action'] == 'DoNothing'
    node, box = first_match(data, node, boxes)
    assert node == 'LevelUpgradeCancel'
    assert box == (513, 1260, 52, 19)
    node, _ = first_match(data, node, frame('level_shelf_after_missed_click'))
    assert node == 'LevelClickMyTab'


def test_level_my_tab_missed_click_retries_then_confirms_my_page():
    data = level_pipeline()
    node, _ = first_match(data, 'LevelClickMyTab', frame('level_shelf_after_missed_click'))
    assert node == 'LevelClickMyTabAgain'
    node, _ = first_match(data, node, frame('level_my_return'))
    assert node == 'LevelMyPageReady'
    assert data['LevelClickMyTabAgain']['max_hit'] == 2


def test_level_known_promo_is_confirmed_before_scoped_close():
    data = level_pipeline()
    boxes = frame('level_promo_over_my')
    node, _ = first_match(data, 'LevelMyPageReady', boxes)
    assert node == 'LevelPromoVisible'
    node, box = first_match(data, node, boxes)
    assert node == 'LevelPromoClose'
    assert box == (342, 930, 33, 32)
    with pytest.raises(AssertionError, match='next 无一命中'):
        first_match(data, 'LevelPromoVisible', [('X', (595, 730, 50, 35))])


@pytest.mark.parametrize('current', ['LevelMyPageReady', 'LevelPromoVisible', 'LevelPromoClose'])
def test_level_promo_recovery_captcha_precedes_close(current):
    from tests.test_daily_popups import frame as popup_frame
    boxes = frame('level_promo_over_my') + popup_frame('reward_captcha_with_x')
    node, _ = first_match(level_pipeline(), current, boxes)
    assert node == 'AdSlideCaptchaDetected'


@pytest.mark.parametrize('current', ['LevelBackUntilHome', 'LevelClickMyTab', 'LevelClickMyTabAgain', 'LevelUpgradeVisible', 'LevelUpgradeCancel'])
def test_level_home_recovery_captcha_precedes_background_inputs(current):
    from tests.test_daily_popups import frame as popup_frame
    boxes = frame('level_upgrade_over_shelf') + popup_frame('reward_captcha_with_x')
    node, _ = first_match(level_pipeline(), current, boxes)
    assert node == 'AdSlideCaptchaDetected'


@pytest.mark.parametrize('current', [
    'LevelAdMyPageReturn', 'LevelAdReenterFromMy', 'AdConfirmSkipBrowse',
    'LevelAdUnknownWait',
])
def test_level_reentry_captcha_overlay_precedes_background_click(current):
    from tests.test_daily_popups import frame as popup_frame
    # 组合已有真实验证码提示与此次真实“我的”背景，模拟遮罩仍透出背景入口。
    boxes = frame('level_my_return') + popup_frame('reward_captcha_with_x')
    node, _ = first_match(level_pipeline(), current, boxes)
    assert node == 'AdSlideCaptchaDetected'
