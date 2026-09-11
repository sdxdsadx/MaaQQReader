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
    # 拟人滑动 + 探针标定：主段（探针 20-40px）+ 回正 + 主滑 + 回正 = 4 次 swipe。
    assert len(device.calls) == 4
    x0, y0, x1, y1, duration = device.calls[0]
    assert x0 == 190 and y0 == 1000
    probe_px = x1 - 190
    assert 20 <= probe_px <= 50  # probe(20-40) + 拟人过冲(3-8)
    assert 150 <= duration <= 900
    # 主滑段：从探针终点滑向缺口（修正距离 = (raw-probe)/scale，scale≥1）。
    sx2, sy2, x1b, y1b, dur_b = device.calls[2]
    assert abs(sx2 - x1) <= 10 and abs(sy2 - 1000) <= 4  # 回正段目标有 ±1px 抖动
    corrected = x1b - sx2
    assert corrected <= (440 - 190) + 10  # 修正距离 ≈ 原始屏幕差（合成图 scale=1）
    assert 150 <= dur_b <= 900


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

