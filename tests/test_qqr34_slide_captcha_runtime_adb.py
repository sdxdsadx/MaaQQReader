"""滑块验证码求解器的 adb 端点解析回归（2026-10-01 实机 ConfigError）。

触发：``DailyAdFlow_20261001_173332_121299.json`` 在 ``captcha.detected`` 之后
立刻 ``未预期异常: ConfigError: 配置文件不存在: configs\\qqreader.local.json``，
任务被判 FAILED（exit 2），滑块根本没滑出去。根因是 ``_sendevent_track`` 写死
相对路径读本机配置，工作目录不是仓库根目录时必然抛错。

这里只覆盖「端点从哪来 / 取不到时怎么降级 / 求解失败不崩任务」这三件事，
识别算法本身的回归在 ``tests/test_qqr29_captcha.py``。
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from qqreader.captcha.slide import (
    SlideCaptchaSolver,
    SlideInputUnavailable,
    _adb_endpoint_from_device,
)
from qqreader.page.observation import PageObservation
from qqreader.page.states import RunState
from tests.helpers import make_context

REAL_CAPTCHA_SHOTS = (
    Path(r"G:\project_X\runtime\screenshots\20261001"
         r"\DailyAdFlow_20261001_192252_744543_006_CAPTCHA_DETECTED.png"),
    Path(r"G:\project_X\runtime\screenshots\20261002"
         r"\DailyAdFlow_20261002_050425_787742_009_CAPTCHA_DETECTED.png"),
    Path(r"G:\project_X\runtime\screenshots\20261001"
         r"\DailyAdFlow_20261001_173330_806864_006_CAPTCHA_DETECTED.png"),
)


class _RecordingDevice:
    """假设备：记录 device.swipe 调用；可选带一个 Maa 客户端。"""

    def __init__(self, *, client=None) -> None:
        if client is not None:
            self._client = client
        self.swipes = []

    def swipe(self, x0, y0, x1, y1, duration_ms=300):
        self.swipes.append((x0, y0, x1, y1, duration_ms))


def _client_with(adb_path: str, adb_address: str):
    return SimpleNamespace(
        config=SimpleNamespace(adb_path=adb_path, adb_address=adb_address)
    )


def _patch_subprocess(monkeypatch, calls):
    """假 adb：getevent 报出触屏设备，sendevent 一律成功。"""

    def fake_run(command, **kwargs):
        calls.append(command)
        if "getevent" in command:
            return subprocess.CompletedProcess(
                command, 0, "add device 1: /dev/input/event2\n  ABS_MT_POSITION_X\n", ""
            )
        return subprocess.CompletedProcess(command, 0, b"", b"")

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr("qqreader.captcha.slide.time.sleep", lambda seconds: None)


def test_adb_endpoint_read_from_runtime_client() -> None:
    device = _RecordingDevice(client=_client_with("X:/adb.exe", "127.0.0.1:16416"))
    assert _adb_endpoint_from_device(device) == ("X:/adb.exe", "127.0.0.1:16416")


def test_adb_endpoint_absent_without_client() -> None:
    assert _adb_endpoint_from_device(_RecordingDevice()) == (None, None)


def test_sendevent_uses_runtime_endpoint_outside_repo_root(
    tmp_path, monkeypatch
) -> None:
    """回归：工作目录不是仓库根目录时，仍要用**本次运行**的 adb 端点。

    修复前这里会去读 ``configs/qqreader.local.json``（相对当前工作目录），
    直接抛 ``ConfigError``；修复后必须走 Maa 客户端的端点并且不读配置文件。
    """
    monkeypatch.chdir(tmp_path)  # tmp 下没有 configs/qqreader.local.json

    def exploding_load_config(path):
        raise AssertionError(f"不应再按相对路径读配置文件: {path}")

    monkeypatch.setattr("qqreader.config.load_config", exploding_load_config)

    calls = []
    _patch_subprocess(monkeypatch, calls)
    device = _RecordingDevice(client=_client_with("X:/adb.exe", "127.0.0.1:16416"))
    solver = SlideCaptchaSolver(observer=object(), device=device, settle_seconds=0)

    solver._sendevent_track(100, 800, [(5, 14)], 0)

    assert device.swipes == [], "有可用 adb 端点时不应退化为 device.swipe"
    assert calls, "应通过 adb 注入 sendevent"
    assert all(command[0] == "X:/adb.exe" for command in calls)
    assert all("127.0.0.1:16416" in command for command in calls)


def test_sendevent_degrades_to_device_swipe_without_any_endpoint(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "qqreader.captcha.slide._adb_endpoint_from_local_config",
        lambda: (None, None),
    )
    device = _RecordingDevice()
    solver = SlideCaptchaSolver(observer=object(), device=device, settle_seconds=0)

    solver._sendevent_track(100, 800, [(20, 10), (5, 10)], 0)

    assert len(device.swipes) == 1
    x0, y0, x1, y1, _ = device.swipes[0]
    assert (x0, y0, x1, y1) == (100, 800, 125, 800)  # 起点 + 轨迹总位移


def test_sendevent_degrades_when_adb_binary_missing(monkeypatch) -> None:
    """adb 可执行文件不存在（例如换了机器）时降级，不抛异常。"""
    def missing(command, **kwargs):
        raise FileNotFoundError(command[0])

    monkeypatch.setattr(subprocess, "run", missing)
    device = _RecordingDevice()
    solver = SlideCaptchaSolver(
        observer=object(),
        device=device,
        settle_seconds=0,
        adb_path="Z:/nowhere/adb.exe",
        adb_address="127.0.0.1:16416",
    )

    solver._sendevent_track(100, 800, [(10, 10)], 0)

    assert len(device.swipes) == 1


def test_sendevent_raises_input_unavailable_when_device_swipe_also_fails(
    monkeypatch,
) -> None:
    class _DeadDevice:
        def swipe(self, *args, **kwargs):
            raise RuntimeError("设备链路不可用")

    monkeypatch.setattr(
        "qqreader.captcha.slide._adb_endpoint_from_local_config",
        lambda: (None, None),
    )
    solver = SlideCaptchaSolver(
        observer=object(), device=_DeadDevice(), settle_seconds=0
    )

    with pytest.raises(SlideInputUnavailable, match="设备链路不可用"):
        solver._sendevent_track(100, 800, [(10, 10)], 0)


def _real_captcha_bytes() -> bytes:
    for path in REAL_CAPTCHA_SHOTS:
        if path.is_file():
            return path.read_bytes()
    pytest.skip("本机没有 2026-10-01/10-02 的真实滑动验证码截图")


def test_solve_reports_unsolved_instead_of_crashing_on_input_failure(
    monkeypatch,
) -> None:
    """输入链路不可用时返回 solved=False（→ 验证码阻塞），不是抛异常。"""
    frame = _real_captcha_bytes()

    class _Observer:
        last_screenshot = SimpleNamespace(data=frame)

        def observe(self, context, *, deep=False):
            return PageObservation(ocr_texts=("安全验证", "拖动下方滑块完成拼图"))

        def save_last_screenshot(self, path):
            return None

    class _DeadDevice:
        def swipe(self, *args, **kwargs):
            raise RuntimeError("设备链路不可用")

        def tap_point(self, *args, **kwargs):
            raise AssertionError("不应刷新")

    monkeypatch.setattr(
        "qqreader.captcha.slide._adb_endpoint_from_local_config",
        lambda: (None, None),
    )
    solver = SlideCaptchaSolver(
        observer=_Observer(), device=_DeadDevice(), settle_seconds=0
    )

    result = solver.solve(make_context(PageObservation.empty(), run_state=RunState.CAPTCHA))

    assert result.solved is False
    assert "无法下发滑动输入" in result.reason
    assert "设备链路不可用" in result.reason


def test_solve_on_real_captcha_frame_with_runtime_endpoint(monkeypatch) -> None:
    """端到端回归：真实验证码帧 + 运行时 adb 端点 → 滑完确认消失 → solved=True。

    修复前这条路径会在 ``_sendevent_track`` 里抛 ``ConfigError``（cwd 不是仓库
    根目录时），或被人工模式短路，永远走不到「确认验证码消失」。
    """
    frame = _real_captcha_bytes()
    texts = [("安全验证", "拖动下方滑块完成拼图"), ()]

    class _Observer:
        last_screenshot = SimpleNamespace(data=frame)
        index = 0

        def observe(self, context, *, deep=False):
            current = texts[min(self.index, len(texts) - 1)]
            self.index += 1
            return PageObservation(ocr_texts=current)

        def save_last_screenshot(self, path):
            return None

    calls = []
    _patch_subprocess(monkeypatch, calls)
    device = _RecordingDevice(client=_client_with("X:/adb.exe", "127.0.0.1:16416"))
    solver = SlideCaptchaSolver(observer=_Observer(), device=device, settle_seconds=0)

    result = solver.solve(make_context(PageObservation.empty(), run_state=RunState.CAPTCHA))

    assert result.solved is True
    assert "已滑动" in result.reason
    assert result.data["distance"] > 0
    assert device.swipes == [], "精确注入可用时不应退化为 device.swipe"
