"""issue #12 共享可观测性原语（run_task.py 路径：GUI + CLI）。

``scripts/run_task.py`` 是 GUI（子进程）与 CLI 共用的入口，本模块为它提供：

* 文件日志：:func:`setup_task_file_logging` 把任务日志写到文件，stdout
  保持干净（GUI 依赖输出协议解析）；
* 崩溃兜底记录：:func:`write_failure_record` 在 runner 异常退出、没能走
  正常记录流程时，也能写出一份含 ``device_error`` 字段的可排障 JSON 记录；
* 截屏失败护栏：:class:`DeviceScreencapGuard` 包裹观测器，连续 N 次截屏
  失败才上抛异常（判定设备级失败），否则降级为 ``device_online=False``
  的观测，交给主循环的停滞/恢复阶梯继续处理。

本模块不 import MAA 相关代码，保证在设备层不可用时也能被导入。
"""

from __future__ import annotations

import json
import logging
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Optional

if TYPE_CHECKING:  # pragma: no cover
    from qqreader.contract.outcome import TaskOutcome

#: 设备级失败的任务结果值（与 ``TaskOutcome.DEVICE_ERROR`` 一致）。
DEVICE_ERROR_OUTCOME = "DEVICE_ERROR"


def _safe_task_name(name: str) -> str:
    safe = re.sub(r"[^0-9A-Za-z._-]+", "_", name).strip("_")
    return safe or "task"


def setup_task_file_logging(log_dir: Path, task: str) -> logging.Handler:
    """把 ``qqreader.task`` logger 的 INFO 日志写入 ``log_dir`` 下的文件。

    返回新增的 handler（测试可自行 ``removeHandler``）。目录创建失败时打印
    警告并返回 ``logging.NullHandler()``，不影响任务执行。
    """
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        print(
            "[gui-observability] 无法创建日志目录 %s: %s" % (log_dir, exc),
            file=sys.stderr,
        )
        return logging.NullHandler()

    filename = "gui_%s_%s.log" % (
        _safe_task_name(task),
        datetime.now().strftime("%Y%m%d_%H%M%S"),
    )
    handler = logging.FileHandler(log_dir / filename, encoding="utf-8")
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    )
    logger = logging.getLogger("qqreader.task")
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    # GUI 依赖 stdout/stderr 协议，日志只落文件、不向控制台传播。
    logger.propagate = False
    return handler


def write_failure_record(
    record_dir: Path,
    screenshot_dir: Path,
    task: str,
    outcome: "TaskOutcome",
    reason: str,
    *,
    started_at: float,
    ended_at: float,
    device_error: str = "",
) -> Optional[Path]:
    """异常退出时的兜底任务记录；返回记录路径，写不出时返回 ``None``。

    在正常落盘之外独立走一次 :class:`FileRunRecorder.finish`，并在写出后
    往 JSON 里注入 ``device_error`` 字段（区分设备级失败与任务逻辑失败）。
    """
    from qqreader.contract.outcome import TaskResult
    from qqreader.page.states import PageState, RunState
    from qqreader.runner.recording import FileRunRecorder, RecordingConfig

    result = TaskResult(
        task=task,
        outcome=outcome,
        reason=reason,
        started_at=started_at,
        ended_at=ended_at,
        steps=0,
        final_state=PageState.UNKNOWN,
        run_state=RunState.FAILED,
    )
    recorder = FileRunRecorder(
        RecordingConfig(
            record_dir=record_dir,
            screenshot_dir=screenshot_dir,
            retention_days=30,
        )
    )
    try:
        path = recorder.finish(result)
    except Exception as exc:  # noqa: BLE001 - 兜底记录失败不掩盖原始异常
        print(
            "[gui-observability] 兜底记录写入失败: %s" % (exc,),
            file=sys.stderr,
        )
        return None
    if path is None:
        return None

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["device_error"] = device_error
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError as exc:
        print(
            "[gui-observability] 注入 device_error 失败: %s" % (exc,),
            file=sys.stderr,
        )
    return path


class DeviceScreencapGuard:
    """连续截屏失败护栏的观测器包装。

    未定义的属性（例如 ``save_last_screenshot`` / ``last_screenshot`` /
    ``catalog``）一律转发给内部观测器。连续截屏失败达到
    ``max_consecutive_failures`` 次时把异常上抛，让 runner 判定为设备级
    失败；未达到时返回降级的 ``PageObservation``（``device_online=False``），
    交给 runner 主循环的停滞与恢复阶梯继续处理。
    """

    def __init__(
        self,
        inner: Any,
        *,
        max_consecutive_failures: int = 3,
        log: Optional[Callable[[str], None]] = None,
    ) -> None:
        self._inner = inner
        self._max_consecutive_failures = max_consecutive_failures
        self._log = log
        self._consecutive_failures = 0

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)

    def observe(self, context: Any = None, *, deep: bool = False) -> Any:
        try:
            observation = self._inner.observe(context, deep=deep)
        except Exception as exc:  # noqa: BLE001 - 前几次失败须降级而非中断
            self._consecutive_failures += 1
            if self._log is not None:
                self._log(
                    "[screencap-fail %d/%d] %s: %s"
                    % (
                        self._consecutive_failures,
                        self._max_consecutive_failures,
                        type(exc).__name__,
                        exc,
                    )
                )
            if self._consecutive_failures >= self._max_consecutive_failures:
                raise
            return _degraded_observation()
        self._consecutive_failures = 0
        return observation


def _degraded_observation() -> Any:
    """截屏失败时的降级观测：明确标记设备不可达，其余证据为空。"""
    from qqreader.page.observation import PageObservation
    from qqreader.page.states import Orientation

    return PageObservation(
        current_app=None,
        orientation=Orientation.PORTRAIT,
        title=None,
        ocr_texts=(),
        icons={},
        templates={},
        structure={},
        device_online=False,
        captured_at=None,
        screenshot_path=None,
    )
