"""正文前台判定与中断恢复，书架/验证码输入来自真实 OCR 记录。"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import auto_read_30min as arm
from tests.test_daily_entry_20261004 import boxes
from tests.test_daily_popups import FakeClient, frame

READER = '  mCurrentFocus=Window{abc u0 com.qq.reader/com.qq.reader.activity.ReaderPageActivity}'
SHELF = '  mCurrentFocus=Window{def u0 com.qq.reader/com.qq.reader.MainActivity}'


def test_reader_wait_rejects_background_reader_window(monkeypatch):
    dump = SHELF + '\n  Window #6 Window{abc u0 com.qq.reader/com.qq.reader.activity.ReaderPageActivity}'
    monkeypatch.setattr(arm, 'reader_focus', lambda: dump)
    tick = iter([0.0, 0.0, 1.0])
    monkeypatch.setattr(arm.time, 'monotonic', lambda: next(tick))
    monkeypatch.setattr(arm.time, 'sleep', lambda _: None)
    assert arm.wait_reader_page(0.5) is False


def setup_reader(monkeypatch, tmp_path, observed):
    state = {'focus': READER, 'swipes': 0, 'reentries': 0}
    logs = []
    monkeypatch.setattr(arm, '_client', FakeClient([observed]))
    monkeypatch.setattr(arm, '_evidence_dir', tmp_path)
    monkeypatch.setattr(arm, '_allowed_keywords', ('宇智波',))
    monkeypatch.setattr(arm, 'log', logs.append)
    monkeypatch.setattr(arm.time, 'sleep', lambda _: None)
    monkeypatch.setattr(arm, 'reader_focus', lambda: state['focus'])
    monkeypatch.setattr(arm, 'dismiss_blocking_dialogs', lambda: 0)
    monkeypatch.setattr(arm, 'return_to_shelf', lambda: None)
    def adb(*args, **kwargs):
        assert state['focus'] == READER, '禁止在书架/验证码上继续翻页'
        state['swipes'] += 1
        if state['swipes'] == 1:
            state['focus'] = SHELF
        return ''
    def reenter(*args, **kwargs):
        state['reentries'] += 1
        state['focus'] = READER
    monkeypatch.setattr(arm, 'adb', adb)
    monkeypatch.setattr(arm, 'click_target_book', reenter)
    return state, logs


def test_dwell_recovers_confirmed_shelf_without_counting_interrupted_minute(monkeypatch, tmp_path):
    state, logs = setup_reader(monkeypatch, tmp_path, boxes('shelf'))
    arm.dwell(1, 1, 1)
    assert state['reentries'] == 1
    assert state['swipes'] == 4  # 中断的第一次不计时，恢复后补完三次翻页。
    assert sum('1/1 分钟' in s for s in logs) == 1
    assert any('现场记录' in s for s in logs)


def test_dwell_captcha_interrupt_stops_without_reentering_or_swiping(monkeypatch, tmp_path):
    state, _ = setup_reader(monkeypatch, tmp_path, frame('reward_captcha_with_x'))
    with pytest.raises(arm.ReadingBlockedByCaptcha):
        arm.dwell(1, 1, 1)
    assert state['swipes'] == 1
    assert state['reentries'] == 0


def test_dwell_unknown_interrupt_does_not_click_or_resume_counting(monkeypatch, tmp_path):
    state, logs = setup_reader(monkeypatch, tmp_path, [])
    with pytest.raises(RuntimeError):
        arm.dwell(1, 1, 1)
    assert state['swipes'] == 1
    assert state['reentries'] == 0
    assert not any('1/1 分钟' in s for s in logs)


def test_captcha_appearing_during_reentry_blocks_all_navigation(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(arm, '_client', FakeClient([boxes('shelf'), frame('reward_captcha_with_x')]))
    monkeypatch.setattr(arm, '_evidence_dir', tmp_path)
    monkeypatch.setattr(arm, 'reader_focus', lambda: SHELF)
    monkeypatch.setattr(arm, 'log', lambda _: None)
    monkeypatch.setattr(arm.time, 'sleep', lambda _: None)
    monkeypatch.setattr(arm, 'return_to_capturable', lambda **_: None)
    monkeypatch.setattr(arm, 'press_back', lambda: calls.append('BACK'))
    monkeypatch.setattr(arm, 'tap', lambda *xy: calls.append(xy))
    with pytest.raises(arm.ReadingBlockedByCaptcha):
        arm.recover_reader_page(1)
    assert calls == []


@pytest.mark.parametrize('failure', [RuntimeError('navigation failed'), arm.BookNotAllowed('book missing'), KeyboardInterrupt()])
def test_failure_cleanup_preserves_captcha_exit_code(monkeypatch, tmp_path, failure):
    from types import SimpleNamespace
    from qqreader.maa import factory
    from qqreader.runner.exit_codes import EXIT_BLOCKED_BY_CAPTCHA
    closed = []
    logs = []
    client = SimpleNamespace(connect=lambda: None, close=lambda: closed.append(True))
    config = SimpleNamespace(machine=SimpleNamespace(
        adb_path='adb.exe', adb_address='device', screenshot_dir=str(tmp_path)))
    monkeypatch.setattr(sys, 'argv', ['auto_read', '--minutes', '1', '--skip-claim'])
    monkeypatch.setattr(arm, 'load_config', lambda _: config)
    monkeypatch.setattr(factory, 'build_maa_client', lambda _: client)
    monkeypatch.setattr(arm, '_client', None)
    monkeypatch.setattr(arm, '_adb_path', None)
    monkeypatch.setattr(arm, '_adb_address', None)
    monkeypatch.setattr(arm, '_evidence_dir', None)
    monkeypatch.setattr(arm, '_allowed_keywords', ('宇智波',))
    monkeypatch.setattr(arm, 'log', logs.append)
    calls = []
    def return_to_page():
        calls.append(True)
        if len(calls) == 2:
            raise arm.ReadingBlockedByCaptcha('captcha in cleanup')
    def launch():
        raise failure
    monkeypatch.setattr(arm, 'return_to_capturable', return_to_page)
    monkeypatch.setattr(arm, 'launch_app', launch)
    assert arm.main() == EXIT_BLOCKED_BY_CAPTCHA
    assert closed == [True]
    assert any('BLOCKED_BY_CAPTCHA' in line for line in logs)


def test_book_retry_captcha_is_not_swallowed_as_navigation_failure(monkeypatch):
    shelf_without_book = [box for box in boxes('shelf') if '宇智波' not in box[0]]
    calls = []
    monkeypatch.setattr(arm, '_client', FakeClient([
        shelf_without_book, shelf_without_book, frame('reward_captcha_with_x')]))
    monkeypatch.setattr(arm, '_evidence_dir', None)
    monkeypatch.setattr(arm, 'log', lambda _: None)
    monkeypatch.setattr(arm.time, 'sleep', lambda _: None)
    monkeypatch.setattr(arm, 'return_to_capturable', lambda **_: None)
    monkeypatch.setattr(arm, 'press_back', lambda: calls.append('BACK'))
    monkeypatch.setattr(arm, 'tap', lambda *xy: calls.append(xy))
    with pytest.raises(arm.ReadingBlockedByCaptcha):
        arm.click_target_book()
    assert calls == []
