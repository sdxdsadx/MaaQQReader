"""ADB 预检测试。"""

from __future__ import annotations

import subprocess

from qqreader.maa import adb


def test_ensure_device_ready_success(monkeypatch) -> None:
    monkeypatch.setattr(adb, "connect_device", lambda *a, **k: True)
    monkeypatch.setattr(adb, "wait_for_boot", lambda *a, **k: True)
    ready, detail = adb.ensure_device_ready("adb.exe", "127.0.0.1:16384")
    assert ready is True
    assert "boot_completed=1" in detail


def test_ensure_device_ready_connect_failure(monkeypatch) -> None:
    monkeypatch.setattr(adb, "connect_device", lambda *a, **k: False)
    monkeypatch.setattr(adb, "wait_for_boot", lambda *a, **k: False)
    ready, detail = adb.ensure_device_ready("adb.exe", "127.0.0.1:16384")
    assert ready is False
    assert "connect 失败" in detail


def test_run_adb_handles_missing_executable(monkeypatch) -> None:
    def _raise(*args, **kwargs):
        raise OSError("missing adb")

    monkeypatch.setattr(subprocess, "run", _raise)
    assert adb.run_adb("missing-adb.exe", "devices") is None


def test_capture_ready_requires_png_signature(monkeypatch) -> None:
    monkeypatch.setattr(adb, "_screencap_bytes", lambda *a, **k: b"\x89PNG" + b"x" * 2000)
    assert adb.capture_ready("adb.exe", "127.0.0.1:16384") is True
    monkeypatch.setattr(adb, "_screencap_bytes", lambda *a, **k: b"")
    assert adb.capture_ready("adb.exe", "127.0.0.1:16384") is False


def test_ensure_maa_ready_short_circuits_on_device_failure(monkeypatch) -> None:
    monkeypatch.setattr(adb, "ensure_device_ready", lambda *a, **k: (False, "offline"))
    ready, detail = adb.ensure_maa_ready("adb.exe", "127.0.0.1:16384")
    assert ready is False
    assert detail == "offline"
