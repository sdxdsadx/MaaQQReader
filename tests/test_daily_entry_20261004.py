"""10-04 真实 OCR 回放：游戏必须点在线时长任务，不能误点充值行。"""
import json
from pathlib import Path

import pytest

from qqreader.tasks.game import build_game_contract
from tests.helpers import SimulatedDevice, make_context, make_recognizer
from tests.test_daily_popups import FakeClient, _context, _game_adapter, frame

FRAMES = json.loads((Path(__file__).parent / 'fixtures/daily_entry_20261004.json').read_text(encoding='utf-8'))


def boxes(name):
    return [(text, tuple(box)) for text, box in FRAMES[name]['boxes']]


@pytest.mark.parametrize('name,expected', [('game_bottom', (593, 1042)), ('game_top', (592, 156))])
def test_game_opens_online_duration_row_with_two_identical_buttons(name, expected):
    observed = boxes(name)
    device = SimulatedDevice()
    client = FakeClient([observed])
    adapter = _game_adapter(device, client)
    ctx = _context(observed)
    step = adapter.advance(ctx)
    assert client.clicks == [expected]
    assert device.calls == []  # 不能再用全屏 OCR 最佳匹配或固定坐标。
    assert step.progress
    assert ctx.get('game_started_at') is None
    assert not build_game_contract().success_condition.evaluate(ctx).satisfied


def test_game_does_not_click_recharge_when_online_duration_row_missing():
    observed = [(t, b) for t, b in boxes('game_top') if not ('玩游戏领赠币' in t or '20分钟' in t or b[1] == 144)]
    client = FakeClient([observed])
    device = SimulatedDevice()
    ctx = _context(observed)
    _game_adapter(device, client).advance(ctx)
    assert client.clicks == []
    assert not any(call[0] in ('tap_feature', 'tap_point') for call in device.calls)
    assert ctx.get('game_entry_scrolls') == 1


def test_game_fresh_frame_captcha_does_not_click_background_button():
    observed = boxes('game_top')
    client = FakeClient([observed + frame('reward_captcha_with_x')])
    device = SimulatedDevice()
    _game_adapter(device, client).advance(_context(observed))
    assert client.clicks == []
    assert device.calls == []


def test_game_returning_to_launcher_reopens_reader_without_losing_exit_state():
    from qqreader.page.observation import PageObservation
    from qqreader.page.states import Orientation
    device = SimulatedDevice()
    observed = PageObservation(current_app='com.mumu.launcher', orientation=Orientation.PORTRAIT,
                               ocr_texts=tuple(t for t, _ in boxes('launcher')))
    ctx = make_context(observed)
    ctx.update_data(game_exit_done=True, game_claim_pending=True, game_started_at=10.0)
    _game_adapter(device, FakeClient([boxes('launcher')])).advance(ctx)
    assert device.calls == [('launch_app', 'com.qq.reader')]
    assert ctx.get('game_exit_done') is True
    assert ctx.get('game_claim_pending') is True
    assert ctx.get('game_started_at') == 10.0


def test_cli_runtime_collects_foreground_package(monkeypatch):
    import sys
    from types import SimpleNamespace
    from qqreader.maa.client import Screenshot, RecoResult
    from qqreader.maa.probes import SubprocessShellRunner
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
    import run_task
    class Client:
        config = SimpleNamespace(adb_path='device-adb.exe', adb_address='device-endpoint')
        def screencap(self):
            return Screenshot(b'frame', 720, 1280)
        def recognize(self, kind, params, shot):
            return RecoResult('OCR', True, detail={'all': [{'text': t, 'box': list(b)} for t, b in boxes('launcher')]})
    def shell(self, args, timeout=None):
        if args[:3] == ('shell', 'pm', 'list'):
            return 'package:com.qq.reader'
        return 'mCurrentFocus=Window{abc u0 com.mumu.launcher/.Launcher}'
    monkeypatch.setattr(SubprocessShellRunner, 'run', shell)
    _, observer, _, _ = run_task._build_runtime(Client(), verbose=False)
    observation = observer.observe()
    assert observation.current_app == 'com.mumu.launcher'
    assert observation.app_installed is True


def test_reading_reward_entry_prefers_real_button_over_duration_description(monkeypatch):
    from qqreader.tasks import reading_reward
    shelf = boxes('shelf_after_reading')
    client = FakeClient([shelf, frame('reward_page_plain')])
    monkeypatch.setattr(reading_reward.time, 'sleep', lambda _: None)
    reading_reward._open_reward_page(client)
    label, (x, y, w, h) = next(item for item in shelf if item[0] == '领20赠币' and item[1][0] > 420)
    assert client.clicks == [(x + w // 2, y + h // 2)]


def test_reading_reward_entry_cancels_exit_dialog_before_finding_shelf(monkeypatch):
    from qqreader.tasks import reading_reward
    dialog = boxes('reading_exit_dialog')
    shelf = boxes('shelf_after_reading')
    client = FakeClient([dialog, shelf, frame('reward_page_plain')])
    monkeypatch.setattr(reading_reward.time, 'sleep', lambda _: None)
    reading_reward._open_reward_page(client)
    cancel = next(box for text, box in dialog if text == '取消')
    entry = next(box for text, box in shelf if text == '领20赠币' and box[0] > 420)
    assert client.keys == []
    assert client.clicks == [(x + w // 2, y + h // 2) for x, y, w, h in (cancel, entry)]


def test_reading_reward_entry_waits_for_real_loading_frame_without_back(monkeypatch):
    from qqreader.tasks import reading_reward
    shelf = boxes('shelf_after_reading')
    client = FakeClient([shelf, boxes('reward_loading'), frame('reward_page_plain')])
    monkeypatch.setattr(reading_reward.time, 'sleep', lambda _: None)
    reading_reward._open_reward_page(client)
    assert len(client.clicks) == 1
    assert client.keys == []
    assert client.swipes == []
