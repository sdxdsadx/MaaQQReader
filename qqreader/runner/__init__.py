"""调度核心：按契约执行任务，不做任务名特判。"""

from .confirmation import (
    CONFIRMATION_LADDER,
    ConfirmationAttempt,
    ConfirmationConfig,
    ConfirmationResult,
    ConfirmationStep,
    PageConfirmer,
)
from .definition import TaskDefinition
from .recording import FileRunRecorder, RecordingConfig, RunRecorder, ScreenshotProvider
from .registry import TaskRegistry
from .runner import PHASE_KEY, RunPhase, RunnerConfig, TaskRunner

__all__ = [
    "CONFIRMATION_LADDER",
    "PHASE_KEY",
    "ConfirmationAttempt",
    "ConfirmationConfig",
    "ConfirmationResult",
    "ConfirmationStep",
    "FileRunRecorder",
    "PageConfirmer",
    "RecordingConfig",
    "RunPhase",
    "RunRecorder",
    "RunnerConfig",
    "ScreenshotProvider",
    "TaskDefinition",
    "TaskRegistry",
    "TaskRunner",
]
