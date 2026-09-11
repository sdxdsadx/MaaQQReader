"""QQR-29：滑动验证码检测、求解与阻塞链路回归测试。"""

from __future__ import annotations

from pathlib import Path

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


def test_detect_slide_finds_track_slider_and_gap() -> None:
    detection = detect_slide(_synthetic_slide_png())
    assert detection.found is True
    assert detection.distance > 0
    assert detection.target[0] > detection.slider_center[0]


def test_slide_solver_swipes_to_gap() -> None:
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

    device = _Device()
    solver = SlideCaptchaSolver(observer=_Observer(), device=device)
    result = solver.solve(
        make_context(PageObservation.empty(), run_state=RunState.CAPTCHA)
    )
    assert result.solved is True
    assert device.calls
    # 拟人滑动：主段 + 回正段（两次 swipe），主段坐标仍指向缺口（含过冲抖动）。
    assert len(device.calls) == 2
    x0, y0, x1, y1, duration = device.calls[0]
    assert x0 == 190 and y0 == 1000
    assert abs(x1 - 440) <= 10 and abs(y1 - 1000) <= 4
    assert 350 <= duration <= 900
    # 回正段：小幅拉回对齐拼图。
    x0b, y0b, x1b, y1b, dur_b = device.calls[1]
    assert x0b == x1 and y0b == y1
    assert abs(x1b - 440) <= 2 and y1b == 1000
    assert 150 <= dur_b <= 350


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

