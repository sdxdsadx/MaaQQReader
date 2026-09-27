"""``scripts/run_task.py`` 子进程退出码约定（QQR-53）。

GUI / ``scripts/daily_all.py`` 只能拿到子进程退出码。过去新流程除 SUCCESS 外
一律返回 2，验证码阻塞、超时、设备错误在串行记录里无法区分，串行调度也就
无法在验证码阻塞时停下。这里给每种结果一个独立退出码：

* 0 / 2 / 3 保持原义：成功 / 任务未成功或参数错误 / 致命错误（设备预检失败、
  配置缺失、未预期异常；自动阅读的白名单拒绝也是 3）；
* 新流程的非成功结果从 10 开始编号，避免与旧流程、自动阅读脚本透传的小数字
  退出码冲突；
* 20 只由交接检查（``HandoffCheck``）返回。
"""

from __future__ import annotations

from ..contract.outcome import TaskOutcome

EXIT_SUCCESS = 0
EXIT_FAILED = 2
EXIT_FATAL = 3
EXIT_BLOCKED_BY_CAPTCHA = 10
EXIT_TIMEOUT = 11
EXIT_DEVICE_ERROR = 12
EXIT_CANCELLED = 13
EXIT_HANDOFF_UNSAFE = 20

_OUTCOME_EXIT_CODES = {
    TaskOutcome.SUCCESS: EXIT_SUCCESS,
    TaskOutcome.FAILED: EXIT_FAILED,
    TaskOutcome.SKIPPED: EXIT_FAILED,
    TaskOutcome.BLOCKED_BY_CAPTCHA: EXIT_BLOCKED_BY_CAPTCHA,
    TaskOutcome.TIMEOUT: EXIT_TIMEOUT,
    TaskOutcome.DEVICE_ERROR: EXIT_DEVICE_ERROR,
    TaskOutcome.CANCELLED: EXIT_CANCELLED,
}

_DESCRIPTIONS = {
    EXIT_SUCCESS: "成功",
    EXIT_FAILED: "任务未成功",
    EXIT_FATAL: "致命错误或书源白名单拒绝",
    EXIT_BLOCKED_BY_CAPTCHA: "验证码阻塞，等待人工",
    EXIT_TIMEOUT: "独立超时",
    EXIT_DEVICE_ERROR: "设备错误",
    EXIT_CANCELLED: "已取消",
    EXIT_HANDOFF_UNSAFE: "交接失败：无法确认安全起点",
}


def exit_code_for_outcome(outcome: TaskOutcome) -> int:
    """把任务结果映射成子进程退出码；未知结果按「任务未成功」处理。"""
    return _OUTCOME_EXIT_CODES.get(outcome, EXIT_FAILED)


def describe_exit_code(code: int) -> str:
    """供串行记录和日志使用的中文说明。"""
    return _DESCRIPTIONS.get(code, f"子进程退出码 {code}")


__all__ = [
    "EXIT_BLOCKED_BY_CAPTCHA",
    "EXIT_CANCELLED",
    "EXIT_DEVICE_ERROR",
    "EXIT_FAILED",
    "EXIT_FATAL",
    "EXIT_HANDOFF_UNSAFE",
    "EXIT_SUCCESS",
    "EXIT_TIMEOUT",
    "describe_exit_code",
    "exit_code_for_outcome",
]
