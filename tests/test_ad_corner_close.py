"""广告播放后从顶部可见 X 退出，避免把右上角静音键当关闭。"""

from __future__ import annotations

import pytest

from qqreader.maa.client import RecoResult, Screenshot
from qqreader.page.feature_keys import DEFAULT_FEATURE_KEYS
from qqreader.page.states import RunState
from qqreader.tasks.ad import AdTaskAdapter, _image_corner_x, build_ad_action_plan
from qqreader.tasks.common import feature_key
from tests.helpers import QQ, SimulatedDevice, ad_playing_observation, make_context
from tests.test_maa_adapter import FAKE_PNG, FakeMaaClient


def _adapter(device: SimulatedDevice, client: FakeMaaClient) -> AdTaskAdapter:
    keys = DEFAULT_FEATURE_KEYS
    return AdTaskAdapter(
        device=device,
        plan=build_ad_action_plan(keys),
        expected_package=QQ,
        popup_feature=feature_key(keys, keys.popup_close),
        navigation_client=client,
    )


def test_after_watch_uses_right_corner_ocr_box() -> None:
    client = FakeMaaClient(
        screenshots=[Screenshot(FAKE_PNG, 720, 1280)],
        recognizer=lambda kind, params, shot: RecoResult(
            kind, True, detail={"all": [{"text": "×", "box": [650, 48, 40, 40]}]}
        ),
    )
    device = SimulatedDevice()
    adapter = _adapter(device, client)
    context = make_context(
        ad_playing_observation(ocr_texts=("广告",)), run_state=RunState.RUNNING
    )

    assert adapter.advance(context).actions == ("WAIT",)
    assert adapter.advance(context).actions == ("TAP_POINT",)
    assert device.calls == [("tap_point", 670, 68)]


@pytest.mark.parametrize("close_x, mute_x", [(48, 679), (679, 48)])
def test_image_close_finds_either_corner_and_rejects_mute(
    close_x: int, mute_x: int
) -> None:
    cv2 = pytest.importorskip("cv2")
    import numpy as np

    image = np.zeros((1280, 720, 3), dtype=np.uint8)
    cv2.circle(image, (close_x, 70), 20, (110, 110, 110), 2)
    cv2.line(image, (close_x - 8, 62), (close_x + 8, 78), (255, 255, 255), 2)
    cv2.line(image, (close_x + 8, 62), (close_x - 8, 78), (255, 255, 255), 2)
    cv2.circle(image, (mute_x, 70), 20, (110, 110, 110), 2)
    cv2.line(image, (mute_x - 6, 63), (mute_x + 6, 77), (255, 255, 255), 2)
    ok, encoded = cv2.imencode(".png", image)
    assert ok
    assert _image_corner_x(encoded.tobytes()) == (close_x, 70)


def test_captcha_on_fresh_frame_blocks_close_click() -> None:
    client = FakeMaaClient(
        screenshots=[Screenshot(FAKE_PNG, 720, 1280)],
        recognizer=lambda kind, params, shot: RecoResult(
            kind, True, detail={"all": [
                {"text": "×", "box": [650, 48, 40, 40]},
                {"text": "安全验证", "box": [80, 370, 100, 30]},
            ]}
        ),
    )
    device = SimulatedDevice()
    adapter = _adapter(device, client)
    context = make_context(
        ad_playing_observation(ocr_texts=("广告",)), run_state=RunState.RUNNING
    )

    assert adapter.advance(context).actions == ("WAIT",)
    assert adapter.advance(context).actions == ("WAIT",)
    assert device.calls == []
