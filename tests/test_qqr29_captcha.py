"""QQR-29：滑动验证码检测、求解与阻塞链路回归测试。"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from qqreader.captcha.slide import SlideCaptchaSolver, detect_slide
from qqreader.page.feature_keys import DEFAULT_FEATURE_KEYS
from qqreader.page.observation import PageObservation
from qqreader.page.states import Orientation, PageState, RunState
from qqreader.tasks.common import captcha_condition
from tests.helpers import QQ, make_context, make_recognizer

cv2 = pytest.importorskip("cv2")
np = pytest.importorskip("numpy")


def _synthetic_slide_png() -> bytes:
    image = np.full((1280, 720, 3), 200, np.uint8)
    # 灰色轨道
    cv2.rectangle(image, (100, 995), (620, 1005), (200, 200, 200), -1)
    # 蓝色滑块
    cv2.rectangle(image, (150, 980), (230, 1020), (255, 100, 50), -1)
    # 深色缺口
    cv2.rectangle(image, (400, 800), (480, 880), (30, 30, 30), -1)
    ok, buffer = cv2.imencode(".png", image)
    assert ok
    return buffer.tobytes()


def _synthetic_issue11_png(*, slider_x: int, gap_top: int = 600) -> bytes:
    image = np.full((1280, 720, 3), 245, np.uint8)
    cv2.rectangle(image, (75, 806), (642, 831), (200, 200, 200), -1)
    cv2.rectangle(
        image, (slider_x, 789), (slider_x + 116, 847), (255, 100, 50), -1
    )
    cv2.rectangle(image, (475, gap_top), (565, gap_top + 65), (30, 30, 30), -1)
    ok, buffer = cv2.imencode(".png", image)
    assert ok
    return buffer.tobytes()


def test_detect_slide_finds_track_slider_and_gap() -> None:
    detection = detect_slide(_synthetic_slide_png())
    assert detection.found is True
    assert detection.distance > 0
    assert detection.target[0] > detection.slider_center[0]


def test_detect_slide_accepts_gap_touching_roi_top() -> None:
    detection = detect_slide(_synthetic_issue11_png(slider_x=109, gap_top=506))
    assert detection.found is True
    assert detection.slider_center == (167, 818)
    assert abs(detection.distance - (520 - detection.slider_center[0])) <= 2


def test_detect_slide_recovers_track_split_by_middle_slider() -> None:
    detection = detect_slide(_synthetic_issue11_png(slider_x=354))
    assert detection.found is True
    assert detection.slider_center == (412, 818)
    assert abs(detection.distance - (520 - detection.slider_center[0])) <= 2


def test_slide_solver_swipes_to_gap(monkeypatch) -> None:
    class _Shot:
        data = _synthetic_slide_png()

    class _Observer:
        last_screenshot = _Shot()

        def observe(self, context, *, deep: bool = False):
            return PageObservation.empty()

        def save_last_screenshot(self, path):
            return None

    class _Device:
        def __init__(self) -> None:
            self.calls = []

        def swipe(self, x0, y0, x1, y1, duration_ms=300):
            self.calls.append((x0, y0, x1, y1, duration_ms))

    # 拦截 sendevent 注入：记录轨迹总位移，验证指向缺口且不真正执行 adb。
    sent = []

    def fake_track(self, sx, sy, track, dy):
        sent.append(track)

    monkeypatch.setattr(SlideCaptchaSolver, "_sendevent_track", fake_track)

    device = _Device()
    solver = SlideCaptchaSolver(observer=_Observer(), device=device, settle_seconds=0)
    result = solver.solve(
        make_context(PageObservation.empty(), run_state=RunState.CAPTCHA)
    )
    assert result.solved is True
    # sendevent 拟人轨迹：合成图 raw=250 → 轨迹终点 = 起点+250（ease 累计=250，
    # 加过冲回调后最终停在 raw）。验证轨迹存在且总位移指向缺口。
    assert sent, "sendevent 轨迹未被调用"
    track = sent[0]
    total_dx = sum(d for d, _ in track)
    assert abs(total_dx - 250) <= 12  # ease 累计 + 过冲 - 回调 ≈ raw
    assert all(dt >= 14 for _, dt in track)  # 每步有自然延时
    assert len(track) >= 12  # 足够多的变速步
    # 旧 device.swipe 路径不再作为主滑动使用。
    assert device.calls == []


def test_slide_solver_recaptures_after_first_detection_failure(monkeypatch) -> None:
    invalid = np.full((1280, 720, 3), 245, np.uint8)
    ok, buffer = cv2.imencode(".png", invalid)
    assert ok
    frames = [buffer.tobytes(), _synthetic_issue11_png(slider_x=109)]

    class _Shot:
        data = frames[0]

    class _Observer:
        last_screenshot = _Shot()
        calls = 0

        def observe(self, context, *, deep: bool = False):
            self.last_screenshot.data = frames[min(self.calls, len(frames) - 1)]
            self.calls += 1
            return PageObservation.empty()

        def save_last_screenshot(self, path):
            return None

    class _Device:
        def swipe(self, *args, **kwargs):
            raise AssertionError("不应退化到 device.swipe")

    sent = []
    monkeypatch.setattr(
        SlideCaptchaSolver,
        "_sendevent_track",
        lambda self, sx, sy, track, dy: sent.append((sx, sy, track, dy)),
    )
    observer = _Observer()
    result = SlideCaptchaSolver(
        observer=observer, device=_Device(), settle_seconds=0
    ).solve(make_context(PageObservation.empty(), run_state=RunState.CAPTCHA))

    assert result.solved is True
    assert observer.calls >= 2
    assert sent


def test_sendevent_batch_retries_once_on_nonzero_return(monkeypatch) -> None:
    import subprocess

    from qqreader import config as config_module
    from qqreader.runtime.clock import FakeClock

    monkeypatch.setattr(
        config_module,
        "load_config",
        lambda path: SimpleNamespace(
            machine=SimpleNamespace(adb_path="adb", adb_address="device")
        ),
    )
    monkeypatch.setattr("qqreader.captcha.slide.time.sleep", lambda seconds: None)
    calls = []

    def fake_run(command, **kwargs):
        calls.append(command)
        if "getevent" in command:
            return subprocess.CompletedProcess(
                command,
                0,
                "add device 1: /dev/input/event2\n  ABS_MT_POSITION_X\n",
                "",
            )
        send_index = len([call for call in calls if "sendevent" in call[-1]])
        return subprocess.CompletedProcess(command, 1 if send_index == 1 else 0, b"", b"")

    monkeypatch.setattr(subprocess, "run", fake_run)
    solver = SlideCaptchaSolver(
        observer=object(), device=object(), settle_seconds=0, clock=FakeClock()
    )
    solver._sendevent_track(100, 800, [(5, 14)], 0)

    send_calls = [call for call in calls if "sendevent" in call[-1]]
    assert len(send_calls) == 4  # down 重试两次，其后 move/up 各一次
    assert send_calls[0] == send_calls[1]


def test_slide_captcha_ocr_confirms_captcha_state() -> None:
    recognizer = make_recognizer()
    observation = PageObservation(
        current_app=QQ,
        orientation=Orientation.PORTRAIT,
        ocr_texts=("安全验证", "拖动下方滑块完成拼图"),
    )
    decision = recognizer.evaluate(observation)
    assert decision.state is PageState.CAPTCHA


def test_captcha_condition_triggers_on_slide_text() -> None:
    observation = PageObservation(
        current_app=QQ,
        orientation=Orientation.PORTRAIT,
        ocr_texts=("安全验证", "拖动下方滑块完成拼图"),
    )
    context = make_context(observation, run_state=RunState.RUNNING)
    assert captcha_condition(DEFAULT_FEATURE_KEYS).evaluate(context).satisfied


def test_detect_slide_on_real_old_captcha_screenshot() -> None:
    path = Path(
        r"G:\project_X\dev\debug\slide_evidence_20260907_142107.png"
    )
    if not path.is_file():
        pytest.skip("本机没有旧工程保存的真实滑动验证码截图")
    detection = detect_slide(path.read_bytes())
    assert detection.found is True
    assert detection.distance > 0


def test_detect_slide_on_issue11_real_screenshots() -> None:
    captcha_detected = Path(
        r"G:\project_X\runtime\screenshots\19700105\DailyAdFlow_19700105_043445_515000_005_CAPTCHA_DETECTED.png"
    )
    blocked = Path(
        r"G:\project_X\runtime\screenshots\19700105\DailyAdFlow_19700105_043454_234000_006_BLOCKED_BY_CAPTCHA.png"
    )
    if not captcha_detected.is_file() or not blocked.is_file():
        pytest.skip("本机没有 issue11 的两张真实滑动验证码截图")

    first = detect_slide(captcha_detected.read_bytes())
    assert first.found is True
    assert first.slider_center == (168, 818)
    assert 335 <= first.distance <= 370

    second = detect_slide(blocked.read_bytes())
    assert second.found is True
