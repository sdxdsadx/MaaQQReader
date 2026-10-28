"""分辨率兼容检查（``qqreader.maa.display``）。

``wm size`` / ``wm density`` 的输出取自 2026-10-28 实机：
MuMu 12 实例 0（日常使用、pipeline 坐标的标定环境）与雷电 9 的实例列表。
"""

from __future__ import annotations

import io

import pytest

from qqreader.maa.client import MaaClientError
from qqreader.maa.display import (
    LEVEL_FAIL,
    LEVEL_OK,
    LEVEL_UNKNOWN,
    LEVEL_WARN,
    REFERENCE_DENSITY,
    REFERENCE_SIZE,
    DisplayInfo,
    assess_display,
    enforce_display,
    parse_wm_density,
    parse_wm_size,
    recommended_density,
    scaled_size,
)

# 2026-10-28 MuMu 12 实例 0 的原始输出。
MUMU_WM_SIZE = "Physical size: 720x1280\n"
MUMU_WM_DENSITY = "Physical density: 240\n"


def test_reference_matches_daily_mumu_instance():
    assert parse_wm_size(MUMU_WM_SIZE) == REFERENCE_SIZE
    assert parse_wm_density(MUMU_WM_DENSITY) == REFERENCE_DENSITY


def test_override_wins_over_physical():
    text = "Physical size: 720x1280\r\nOverride size: 1080x1920\r\n"
    assert parse_wm_size(text) == (1080, 1920)
    assert parse_wm_density("Physical density: 240\nOverride density: 360\n") == 360


def test_unparseable_output_returns_none():
    assert parse_wm_size("error: no devices/emulators found") is None
    assert parse_wm_density("") is None


@pytest.mark.parametrize(
    "size, expected",
    [
        ((720, 1280), (720, 1280)),
        ((1080, 1920), (720, 1280)),
        ((1440, 2560), (720, 1280)),
        ((1080, 2400), (720, 1600)),
        ((1920, 1080), (1280, 720)),
    ],
)
def test_scaled_size_follows_maa_short_side_rule(size, expected):
    assert scaled_size(*size) == expected


@pytest.mark.parametrize(
    "info, level",
    [
        # 标定环境
        (DisplayInfo(720, 1280, 240), LEVEL_OK),
        # 9:16 且 DPI 等比：识别 / 点击可用，滑块 sendevent 坐标是设备像素
        (DisplayInfo(1080, 1920, 360), LEVEL_WARN),
        (DisplayInfo(1440, 2560, 480), LEVEL_WARN),
        # 雷电 9 新建实例的默认值（ldconsole list2 实测 720,1280,320）：版式不同
        (DisplayInfo(720, 1280, 320), LEVEL_FAIL),
        # 9:16 但 DPI 没跟着改
        (DisplayInfo(1080, 1920, 240), LEVEL_FAIL),
        # 20:9 手机比例
        (DisplayInfo(1080, 2400, 360), LEVEL_FAIL),
        # 雷电 9 实例 0（ldconsole list2 实测 1920,1080,320）横屏
        (DisplayInfo(1920, 1080, 320), LEVEL_FAIL),
        (DisplayInfo(1280, 720, 240), LEVEL_FAIL),
    ],
)
def test_assess_display_matrix(info, level):
    result = assess_display(info)
    assert result.level == level, result.render()
    assert result.ok is (level != LEVEL_FAIL)


def test_missing_density_only_checks_ratio():
    assert assess_display(DisplayInfo(720, 1280, None)).level == LEVEL_OK
    assert assess_display(DisplayInfo(1080, 2400, None)).level == LEVEL_FAIL


def test_unknown_display_does_not_block():
    result = assess_display(None)
    assert result.level == LEVEL_UNKNOWN
    assert result.ok


def test_fail_message_suggests_fix():
    result = assess_display(DisplayInfo(720, 1280, 320))
    assert "240" in result.suggestion
    assert recommended_density(1080, 1920) == 360
    assert "横屏" in assess_display(DisplayInfo(1920, 1080, 320)).render()


def test_enforce_strict_raises_on_fail():
    with pytest.raises(MaaClientError, match="分辨率不兼容"):
        enforce_display(
            "adb", "127.0.0.1:5555", mode="strict",
            query=lambda *_: DisplayInfo(1920, 1080, 320), stream=io.StringIO(),
        )


def test_enforce_warn_only_reports():
    out = io.StringIO()
    result = enforce_display(
        "adb", "127.0.0.1:5555", mode="warn",
        query=lambda *_: DisplayInfo(720, 1280, 320), stream=out,
    )
    assert result.level == LEVEL_FAIL
    assert "分辨率检查" in out.getvalue()


def test_enforce_ok_is_silent_and_off_skips_query():
    out = io.StringIO()
    result = enforce_display(
        "adb", "x", mode="strict", query=lambda *_: DisplayInfo(720, 1280, 240), stream=out
    )
    assert result.level == LEVEL_OK and out.getvalue() == ""

    def boom(*_):
        raise AssertionError("off 模式不应查询设备")

    assert enforce_display("adb", "x", mode="off", query=boom).level == LEVEL_UNKNOWN


def test_enforce_reads_env(monkeypatch):
    monkeypatch.setenv("QQREADER_DISPLAY_CHECK", "warn")
    result = enforce_display(
        "adb", "x", query=lambda *_: DisplayInfo(1920, 1080, 320), stream=io.StringIO()
    )
    assert result.level == LEVEL_FAIL


# ------------------------------------------------------- 绕过 Maa 的 adb 点击


def test_device_scale():
    from qqreader.maa.display import device_scale

    assert device_scale(None) == 1.0
    assert device_scale(DisplayInfo(720, 1280, 240)) == 1.0
    assert device_scale(DisplayInfo(1080, 1920, 360)) == 1.5
    assert device_scale(DisplayInfo(1920, 1080, 360)) == 1.5


def test_reading_script_scales_raw_adb_input(monkeypatch):
    """2026-10-28 实机 1080×1920：书架书名 OCR 框 (138,448,312,28) 未换算就 input tap，
    点中了上一行「我的笔记」（设备 y 415–590）而不是书（设备 y≈693）。"""
    import sys
    from pathlib import Path

    scripts = Path(__file__).resolve().parents[1] / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    import auto_read_30min as arm

    calls = []
    monkeypatch.setattr(arm, "adb", lambda *args, **kw: calls.append(args) or "")
    monkeypatch.setattr(arm, "_device_scale", 1.5)
    arm.tap_box((138, 448, 312, 28))
    arm.swipe(360, 1050, 360, 350, 500)
    assert calls[0] == ("shell", "input", "tap", "441", "693")
    assert calls[1] == ("shell", "input", "swipe", "540", "1575", "540", "525", "500")

    calls.clear()
    monkeypatch.setattr(arm, "_device_scale", 1.0)
    arm.tap(294, 462)
    assert calls[0] == ("shell", "input", "tap", "294", "462")
