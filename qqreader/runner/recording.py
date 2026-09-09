"""任务运行记录与关键节点截图（QQR-10 / AGENTS.md §2.4、§3.9、§4）。

本模块只负责**记录证据**，不参与任务成败判定：

* 每次任务写出一份 JSON 记录，包含任务名、开始/结束时间、结果状态、
  失败原因、恢复尝试历史、关键节点截图路径与全部诊断事件；
* 截图与记录默认写到源码目录之外的 ``runtime/screenshots`` /
  ``runtime/records``（由 ``MachineConfig`` 提供，可配置）；
* 保留策略默认 30 天，通过 :class:`RecordingConfig.retention_days` 配置；
* 记录/截图写入失败会被调度核心降级为 ``record.error`` 诊断，**不会**
  把任务改成 SUCCESS，也不会把任务改成 FAILED。

成功依据始终是任务的 ``success_condition``；截图只作为事后证据。
"""

from __future__ import annotations

import json
import re
import shutil
import time
from dataclasses import dataclass, is_dataclass, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional, Protocol

from ..contract.outcome import KeyNodeScreenshot, RecoveryStep, TaskResult
from ..page.states import PageState
from ..runtime.context import TaskContext


class ScreenshotProvider(Protocol):
    """能保存「最近一帧截图」的观测器（例如 ``MaaPageObserver``）。"""

    def save_last_screenshot(self, path: Path) -> Optional[Path]:
        ...


class RunRecorder(Protocol):
    """任务运行记录协议。"""

    def start(self, context: TaskContext) -> None:
        """任务开始。"""

    def capture(
        self,
        context: TaskContext,
        kind: str,
        note: str,
        provider: Optional[ScreenshotProvider] = None,
    ) -> Optional[KeyNodeScreenshot]:
        """记录一个关键节点；返回截图证据（截图失败时 path 为空）。"""

    def recovery(self, context: TaskContext, step: RecoveryStep) -> None:
        """记录一次恢复尝试。"""

    def finish(self, result: TaskResult) -> Optional[Path]:
        """任务结束，落盘记录并返回记录文件路径。"""


@dataclass(frozen=True)
class RecordingConfig:
    """运行记录配置。"""

    record_dir: Path
    screenshot_dir: Path
    retention_days: int = 30
    max_screenshots_per_task: int = 40

    def __post_init__(self) -> None:
        if self.retention_days < 1:
            raise ValueError("retention_days 必须 >= 1")
        if self.max_screenshots_per_task < 1:
            raise ValueError("max_screenshots_per_task 必须 >= 1")


class FileRunRecorder:
    """把任务记录写成 JSON，并把关键节点截图保存为 PNG 文件。

    文件布局::

        <record_dir>/<task>_<timestamp>.json
        <screenshot_dir>/<YYYYMMDD>/<task>_<timestamp>_<seq>_<kind>.png

    ``retention_days`` 内的文件保留；更早的 ``*.json`` / ``*.png`` 会被清理。
    """

    def __init__(self, config: RecordingConfig) -> None:
        self._config = config
        self._screenshots: list[KeyNodeScreenshot] = []
        self._recoveries: list[RecoveryStep] = []
        self._capture_count = 0
        self._sequence = 0
        self._task = "task"
        self._started_at = 0.0
        self._ensure_dirs()
        self.prune()

    @property
    def config(self) -> RecordingConfig:
        return self._config

    # ------------------------------------------------------------------ 协议

    def start(self, context: TaskContext) -> None:
        self._screenshots = []
        self._recoveries = []
        self._capture_count = 0
        self._sequence = 0
        self._task = context.contract.name
        self._started_at = context.started_at
        self._ensure_dirs()
        self.prune()

    def capture(
        self,
        context: TaskContext,
        kind: str,
        note: str,
        provider: Optional[ScreenshotProvider] = None,
    ) -> Optional[KeyNodeScreenshot]:
        if self._capture_count >= self._config.max_screenshots_per_task:
            return None
        self._sequence += 1
        at = context.now
        state = context.state.value if context.decision is not None else PageState.UNKNOWN.value
        target = self._screenshot_target(at, kind)
        saved = self._save_screenshot(target, context, provider)
        shot = KeyNodeScreenshot(
            kind=kind,
            at=at,
            path=str(saved) if saved is not None else "",
            note=note,
            state=state,
        )
        self._screenshots.append(shot)
        self._capture_count += 1
        return shot

    def recovery(self, context: TaskContext, step: RecoveryStep) -> None:
        self._recoveries.append(step)

    def finish(self, result: TaskResult) -> Optional[Path]:
        self._ensure_dirs()
        path = self._record_target(result)
        payload = dict(result.to_record())
        payload["record_path"] = str(path)
        # 兼容直接使用 recorder（未经过 TaskRunner）的调用方：如果 TaskResult
        # 没有带截图/恢复历史，就用 recorder 自己累积的证据补全。
        if not result.screenshots and self._screenshots:
            payload["screenshots"] = [shot.to_dict() for shot in self._screenshots]
        if not result.recovery_history and self._recoveries:
            payload["recovery_history"] = [step.to_dict() for step in self._recoveries]
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, default=_json_default),
            encoding="utf-8",
        )
        self.prune()
        return path

    # ------------------------------------------------------------------ 清理

    def prune(self, now: Optional[float] = None) -> int:
        """删除超过保留期的记录/截图；返回删除文件数。"""
        cutoff = (time.time() if now is None else float(now)) - (
            self._config.retention_days * 86400.0
        )
        removed = 0
        for directory in (self._config.record_dir, self._config.screenshot_dir):
            if not directory.is_dir():
                continue
            for path in sorted(directory.rglob("*")):
                if not path.is_file():
                    continue
                try:
                    if path.stat().st_mtime < cutoff:
                        path.unlink()
                        removed += 1
                except OSError:
                    # 清理失败不影响任务结果；下次运行再试。
                    continue
            _remove_empty_dirs(directory)
        return removed

    # ------------------------------------------------------------------ 内部

    def _ensure_dirs(self) -> None:
        self._config.record_dir.mkdir(parents=True, exist_ok=True)
        self._config.screenshot_dir.mkdir(parents=True, exist_ok=True)

    def _screenshot_target(self, at: float, kind: str) -> Path:
        date = datetime.fromtimestamp(at).strftime("%Y%m%d")
        filename = (
            f"{_safe_name(self._task)}_{_stamp(at)}_"
            f"{self._sequence:03d}_{_safe_name(kind)}.png"
        )
        return self._config.screenshot_dir / date / filename

    def _record_target(self, result: TaskResult) -> Path:
        return self._config.record_dir / (
            f"{_safe_name(result.task)}_{_stamp(result.ended_at or time.time())}.json"
        )

    def _save_screenshot(
        self,
        target: Path,
        context: TaskContext,
        provider: Optional[ScreenshotProvider],
    ) -> Optional[Path]:
        target.parent.mkdir(parents=True, exist_ok=True)
        if provider is not None:
            try:
                saved = provider.save_last_screenshot(target)
            except Exception:  # noqa: BLE001 - 截图失败只影响证据，不影响任务
                saved = None
            if saved is not None:
                return Path(saved)
        source = context.observation.screenshot_path
        if source:
            source_path = Path(source)
            if source_path.is_file():
                try:
                    shutil.copy2(source_path, target)
                    return target
                except OSError:
                    return None
        return None


def _safe_name(value: str) -> str:
    safe = re.sub(r"[^0-9A-Za-z._-]+", "_", value).strip("_")
    return safe or "task"


def _stamp(at: float) -> str:
    return datetime.fromtimestamp(float(at)).strftime("%Y%m%d_%H%M%S_%f")


def _remove_empty_dirs(root: Path) -> None:
    if not root.is_dir():
        return
    for path in sorted(root.rglob("*"), reverse=True):
        if path.is_dir():
            try:
                path.rmdir()
            except OSError:
                continue


def _json_default(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (set, frozenset)):
        return sorted(value, key=str)
    if is_dataclass(value):
        return asdict(value)
    return str(value)
