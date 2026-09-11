"""issue #12 观测性原语与设备冒烟预检（GUI/CLI 共用路径）的单元测试。

锁定行为：

* :func:`setup_task_file_logging` 把 ``qqreader.task`` 的 INFO 日志落盘到
  ``gui_<task>_<时间戳>.log``（stdout 保持干净）；
* ``scripts/run_task.py`` 的设备冒烟预检在 adb 未列出设备、或冒烟截屏抛
  :class:`MaaClientError` 时返回可读的失败详情；
* :class:`DeviceScreencapGuard` 连续截屏失败先降级为
  ``device_online=False`` 的观测、达到阈值才上抛，未定义属性转发内部观测器；
* :func:`write_failure_record` 写出含 ``device_error`` 字段的
  ``DEVICE_ERROR`` 兜底记录（含瞬断重试耗尽路径）。
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any, List

import pytest

from qqreader.contract.outcome import TaskOutcome
from qqreader.maa.client import MaaClientError
from qqreader.runner.gui_observability import (
    DeviceScreencapGuard,
    setup_task_file_logging,
    write_failure_record,
)
from qqreader.runner.retry import BackoffPolicy, RetryExhaustedError, run_with_retry

# scripts/run_task.py 是脚本入口而非包模块：先注入 scripts 目录再导入。
_SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import run_task  # noqa: E402 - 需先注入 scripts 目录


def test_task_log_file_written(tmp_path: Path) -> None:
    """setup_task_file_logging：INFO 日志恰好写入一个 gui_<task>_*.log 文件。"""
    log_dir = tmp_path / "logs"
    handler = setup_task_file_logging(log_dir, "DailyGameFlow")
    logger = logging.getLogger("qqreader.task")
    try:
        logger.info("preflight: smoke ok")
        handler.flush()
    finally:
        logger.removeHandler(handler)
        handler.close()

    files = list(log_dir.glob("gui_DailyGameFlow_*.log"))
    assert len(files) == 1
    assert "preflight: smoke ok" in files[0].read_text(encoding="utf-8")


def _raising_screencap() -> Any:
    raise MaaClientError("screencap broken")


def test_preflight_fails_when_device_not_listed() -> None:
    """adb devices 输出未包含配置地址：预检失败，详情说明 adb devices 未列出设备。"""
    config = SimpleNamespace(
        machine=SimpleNamespace(adb_path="adb", adb_address="127.0.0.1:16384")
    )
    # client 必须不被触达：一旦调用 connect/screencap 立即失败。
    client = SimpleNamespace(connect=lambda: 1 / 0, screencap=lambda: 1 / 0)

    ok, detail = run_task.run_device_preflight(
        client,
        config,
        BackoffPolicy(max_retries=0),
        adb_probe=lambda *a, **k: SimpleNamespace(
            stdout="List of devices attached\n", returncode=0
        ),
    )

    assert ok is False
    assert "adb devices" in detail


def test_preflight_fails_on_screencap_error() -> None:
    """adb 已列出设备但冒烟截屏抛 MaaClientError：预检失败，详情带原始错误。"""
    config = SimpleNamespace(
        machine=SimpleNamespace(adb_path="adb", adb_address="127.0.0.1:16384")
    )
    client = SimpleNamespace(connect=lambda: True, screencap=_raising_screencap)

    ok, detail = run_task.run_device_preflight(
        client,
        config,
        BackoffPolicy(max_retries=0),
        adb_probe=lambda *a, **k: SimpleNamespace(
            stdout="List of devices attached\n127.0.0.1:16384\tdevice\n",
            returncode=0,
        ),
    )

    assert ok is False
    assert "screencap broken" in detail


class _BrokenObserver:
    """总是截屏失败的假观测器；last_screenshot 用于验证属性转发。"""

    last_screenshot: Any = "sentinel"

    def observe(self, context: Any = None, *, deep: bool = False) -> Any:
        raise MaaClientError("screencap broken")


def test_screencap_guard_degrades_then_raises() -> None:
    """前 N-1 次截屏失败降级为 device_online=False 观测，第 N 次上抛。"""
    logs: List[str] = []
    guard = DeviceScreencapGuard(
        _BrokenObserver(), max_consecutive_failures=3, log=logs.append
    )

    first = guard.observe(None)
    assert first.device_online is False
    second = guard.observe(None)
    assert second.device_online is False
    with pytest.raises(MaaClientError):
        guard.observe(None)

    # 第 1/2 次失败降级，第 3 次失败在上抛前也必须留痕（共 3 条）。
    assert len(logs) == 3
    assert "[screencap-fail 3/3]" in logs[-1]
    assert all("[screencap-fail" in entry for entry in logs)
    assert guard.last_screenshot == "sentinel"


def test_failure_record_written_with_device_error(tmp_path: Path) -> None:
    """兜底记录：DEVICE_ERROR 结果 + 注入的 device_error 字段可在 JSON 中读回。"""
    path = write_failure_record(
        tmp_path / "records",
        tmp_path / "shots",
        "DailyGameFlow",
        TaskOutcome.DEVICE_ERROR,
        "boom reason",
        started_at=1000.0,
        ended_at=1005.0,
        device_error="MaaClientError: x",
    )

    assert path is not None
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["outcome"] == "DEVICE_ERROR"
    assert payload["device_error"] == "MaaClientError: x"
    assert payload["task"] == "DailyGameFlow"


def test_retry_exhausted_maps_to_device_error_record(tmp_path: Path) -> None:
    """瞬断重试耗尽：RetryExhaustedError 转写为带 device_error 的 DEVICE_ERROR 记录。"""

    def always_reset() -> str:
        raise ConnectionResetError("connection reset by peer")

    with pytest.raises(RetryExhaustedError) as excinfo:
        run_with_retry(always_reset, BackoffPolicy(base_delay=0, max_retries=1))
    exc = excinfo.value

    path = write_failure_record(
        tmp_path / "records",
        tmp_path / "shots",
        "DailyGameFlow",
        TaskOutcome.DEVICE_ERROR,
        "设备/链路瞬断重试耗尽: " + str(exc.last_error),
        started_at=1000.0,
        ended_at=1005.0,
        device_error=str(exc.last_error),
    )

    assert path is not None
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["outcome"] == "DEVICE_ERROR"
    assert "connection reset" in payload["device_error"]
