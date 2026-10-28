"""不同分辨率下的识别与点击坐标：真实截图 + 真实 MaaFramework OCR。

夹具 ``fixtures/images/reward_home_720x1280_20261019.png`` 是 2026-10-19 MuMu 12
实机（720×1280 / 240 DPI）的奖励页截图。把它放大成 1080×1920、1440×2560 后交给
Maa 自定义控制器（``maa_short_side=720``），断言：

* Maa 截图都被缩放回 720×1280；
* OCR 读到同样的关键文字，框的位置与 720 原图一致（容差 6px）；
* 在 720 坐标系里点击，控制器收到的是按比例放大后的设备坐标。

需要 MaaFramework 运行时：设 ``QQREADER_MAA_RUNTIME_DIR``（含 ``MaaFramework.dll``，
资源默认取其下 ``resource/``），或仓库根目录有 ``dev/``；都没有时跳过。
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, Tuple

import pytest

from qqreader.gui import cover

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "images" / "reward_home_720x1280_20261019.png"
KEY_TEXTS = ("每日阅读领赠币", "明日再来", "立即参与", "规则")
SIZES = ((720, 1280), (1080, 1920), (1440, 2560))


def _runtime_dir() -> Path:
    for raw in (os.environ.get("QQREADER_MAA_RUNTIME_DIR"), str(REPO_ROOT / "dev")):
        if raw and (Path(raw) / "MaaFramework.dll").is_file() and (Path(raw) / "resource").is_dir():
            return Path(raw)
    pytest.skip("没有 MaaFramework 运行时（设 QQREADER_MAA_RUNTIME_DIR）")


def _scaled_png(width: int, height: int) -> bytes:
    cv2 = pytest.importorskip("cv2")
    image = cv2.imread(str(FIXTURE))
    assert image is not None and image.shape[:2] == (1280, 720)
    if (width, height) != (720, 1280):
        image = cv2.resize(image, (width, height), interpolation=cv2.INTER_CUBIC)
    ok, encoded = cv2.imencode(".png", image)
    assert ok
    return encoded.tobytes()


def _ocr_boxes(runtime: Path, png: bytes) -> Tuple[Tuple[int, int], Dict[str, Tuple[int, int, int, int]], Tuple]:
    from qqreader.maa.ctypes_client import CtypesMaaClient, CtypesMaaConfig

    config = CtypesMaaConfig(
        runtime_dir=runtime,
        resource_dir=runtime / "resource",
        controller="custom",
        custom_images=(png,),
        short_side=720,
    )
    with CtypesMaaClient(config) as client:
        shot = client.screencap()
        result = client.recognize("OCR", {}, shot)
        boxes = {}
        for item in result.detail.get("all") or []:
            text = str(item.get("text", ""))
            for key in KEY_TEXTS:
                if key in text and key not in boxes:
                    boxes[key] = tuple(item["box"])
        client.click(360, 640)
        click = client.custom_calls[-1]
    return (shot.width, shot.height), boxes, click


@pytest.fixture(scope="module")
def results():
    runtime = _runtime_dir()
    return {size: _ocr_boxes(runtime, _scaled_png(*size)) for size in SIZES}


@pytest.mark.parametrize("size", SIZES)
def test_screenshot_scaled_to_reference(results, size):
    assert results[size][0] == (720, 1280)


@pytest.mark.parametrize("size", SIZES)
def test_ocr_finds_same_texts_at_same_place(results, size):
    reference = results[(720, 1280)][1]
    assert set(reference) == set(KEY_TEXTS), reference
    boxes = results[size][1]
    assert set(boxes) == set(KEY_TEXTS), boxes
    for key in KEY_TEXTS:
        rx, ry, rw, rh = reference[key]
        x, y, w, h = boxes[key]
        # 比较中心点：放大再缩回后框的边缘会差几个像素
        assert abs((x + w / 2) - (rx + rw / 2)) <= 6, (key, reference[key], boxes[key])
        assert abs((y + h / 2) - (ry + rh / 2)) <= 6, (key, reference[key], boxes[key])


@pytest.mark.parametrize("size", SIZES)
def test_click_mapped_to_device_pixels(results, size):
    width, height = size
    assert results[size][2] == ("click", 360 * width // 720, 640 * height // 1280)


# ------------------------------------------------------------- 听书封面截取


@pytest.mark.parametrize("size", SIZES)
def test_cover_capture_normalized_to_short_side_720(size):
    cv2 = pytest.importorskip("cv2")
    import numpy as np

    png = cover.normalize_short_side(_scaled_png(*size))
    image = cv2.imdecode(np.frombuffer(png, dtype=np.uint8), cv2.IMREAD_COLOR)
    assert image.shape[:2] == (1280, 720)


def test_cover_normalize_keeps_reference_bytes_and_bad_data():
    original = FIXTURE.read_bytes()
    assert cover.normalize_short_side(original) is original
    assert cover.normalize_short_side(b"\x89PNG\r\n") == b"\x89PNG\r\n"
