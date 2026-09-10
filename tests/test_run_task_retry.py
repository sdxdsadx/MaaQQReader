"""运行期瞬断重试原语：分类边界、指数退避、重试日志与耗尽语义（QQR-36 / issue #8）。

锁定行为：

* 可重试的瞬断（连接重置、adb 断连、设备离线等）按指数退避重试，
  每次重试输出「第 N 次重试 / 原因 / 等待秒数」日志；
* 重试耗尽抛 ``RetryExhaustedError``（携带总尝试次数与最后异常，``__cause__``
  指向最后异常），与「致命错误原样上抛」区分开；
* 致命错误（取消 / 契约 / 配置）与未知异常一律不重试，立即上抛。

所有用例都不真实等待：退避要么用 ``base_delay=0``，要么注入 ``FakeClock``。
"""

from __future__ import annotations

import errno
from typing import Callable, List, Sequence, Tuple

import pytest

from qqreader.config.errors import ConfigError
from qqreader.errors import Cancelled, ContractViolation
from qqreader.runner.retry import (
    BackoffPolicy,
    RetryExhaustedError,
    is_retryable,
    run_with_retry,
)
from qqreader.runtime.clock import FakeClock

# 模拟 Windows 下的 WSAECONNRESET（errno.ECONNRESET 在 Windows 上即 10054）。
_RESET_ERRNO = 10054


def _reset_error() -> ConnectionResetError:
    return ConnectionResetError(_RESET_ERRNO, "远程主机强迫关闭了一个现有的连接")


def _scripted_func(
    errors: Sequence[BaseException], result: str = "任务完成"
) -> Tuple[Callable[[], str], List[int]]:
    """脚本化被测函数：前 ``len(errors)`` 次依次抛出对应异常，之后返回 result。"""
    calls: List[int] = []

    def func() -> str:
        calls.append(1)
        if len(calls) <= len(errors):
            raise errors[len(calls) - 1]
        return result

    return func, calls


def _always_fail(
    factory: Callable[[], BaseException],
) -> Tuple[Callable[[], str], List[int], List[BaseException]]:
    """始终失败的被测函数：每次调用新建并抛出异常，返回 (func, calls, errors)。"""
    calls: List[int] = []
    errors: List[BaseException] = []

    def func() -> str:
        calls.append(1)
        error = factory()
        errors.append(error)
        raise error

    return func, calls, errors


# --------------------------------------------------------------------- 重试后成功


def test_retryable_error_retries_then_succeeds() -> None:
    """瞬断两次后第三次成功：返回原值，重试日志恰好两条且编号递增。"""
    func, calls = _scripted_func([_reset_error(), _reset_error()])
    logs: List[str] = []

    result = run_with_retry(func, BackoffPolicy(base_delay=0), log=logs.append)

    assert result == "任务完成"
    assert len(calls) == 3
    assert len(logs) == 2
    assert logs[0].startswith("第 1 次重试")
    assert logs[1].startswith("第 2 次重试")
    assert "原因: ConnectionResetError" in logs[0]
    assert "等待 0 秒" in logs[0]


def test_backoff_waits_use_injected_clock() -> None:
    """默认退避走注入的 Clock：等待时长 2s、4s 递增，日志与之一致。"""
    func, calls = _scripted_func([_reset_error(), _reset_error()])
    clock = FakeClock()
    logs: List[str] = []

    result = run_with_retry(func, BackoffPolicy(), log=logs.append, clock=clock)

    assert result == "任务完成"
    assert len(calls) == 3
    assert clock.sleeps == [2.0, 4.0]
    assert "等待 2 秒" in logs[0]
    assert "等待 4 秒" in logs[1]


# --------------------------------------------------------------------- 重试耗尽


def test_exhausted_raises_with_attempts_and_cause() -> None:
    """重试耗尽：抛 RetryExhaustedError，携带总尝试次数与最后异常，__cause__ 链保留。"""
    func, calls, errors = _always_fail(_reset_error)
    logs: List[str] = []

    with pytest.raises(RetryExhaustedError) as excinfo:
        run_with_retry(func, BackoffPolicy(base_delay=0, max_retries=2), log=logs.append)

    assert excinfo.value.attempts == 3  # 1 次初始 + 2 次重试
    assert excinfo.value.last_error is errors[-1]
    assert excinfo.value.__cause__ is errors[-1]
    assert isinstance(excinfo.value.__cause__, ConnectionResetError)
    assert len(calls) == 3
    assert len(logs) == 2  # 每次重试各一条日志，耗尽不再记


def test_total_calls_capped_at_initial_plus_max_retries() -> None:
    """max_retries=3 语义：总计最多 1 次初始 + 3 次重试 = 4 次调用。"""
    func, calls, errors = _always_fail(lambda: OSError("adb: device offline（设备离线）"))
    logs: List[str] = []

    with pytest.raises(RetryExhaustedError) as excinfo:
        run_with_retry(func, BackoffPolicy(base_delay=0, max_retries=3), log=logs.append)

    assert len(calls) == 4
    assert excinfo.value.attempts == 4
    assert excinfo.value.last_error is errors[-1]
    assert len(logs) == 3


# --------------------------------------------------------------------- 不重试


def test_contract_violation_raised_immediately() -> None:
    """契约错误属开发期错误：原实例直接上抛，只调用一次，不产生重试日志。"""
    error = ContractViolation("契约字段缺失")
    func, calls = _scripted_func([error])
    logs: List[str] = []

    with pytest.raises(ContractViolation) as excinfo:
        run_with_retry(func, BackoffPolicy(base_delay=0, max_retries=5), log=logs.append)

    assert excinfo.value is error
    assert len(calls) == 1
    assert logs == []


def test_missing_config_file_raised_immediately() -> None:
    """配置文件缺失（路径含 config/*.json）属配置错误：不重试，原实例上抛。"""
    error = FileNotFoundError(errno.ENOENT, "缺少配置文件", r"G:\project_X\config\task.json")
    func, calls = _scripted_func([error])
    logs: List[str] = []

    with pytest.raises(FileNotFoundError) as excinfo:
        run_with_retry(func, BackoffPolicy(base_delay=0), log=logs.append)

    assert excinfo.value is error
    assert len(calls) == 1
    assert logs == []


def test_unknown_error_raised_immediately() -> None:
    """未知异常默认不重试：宁可快失败，也不在不确定的错误上空转。"""
    error = ValueError("普通业务错误")
    func, calls = _scripted_func([error])

    with pytest.raises(ValueError) as excinfo:
        run_with_retry(func, BackoffPolicy(base_delay=0))

    assert excinfo.value is error
    assert len(calls) == 1


# --------------------------------------------------------------------- 退避间隔


def test_next_delay_doubles_then_clamps() -> None:
    """退避间隔 = base * factor ** attempt（2/4/8/16），以 max_delay 截断。"""
    policy = BackoffPolicy()
    assert [policy.next_delay(attempt) for attempt in range(4)] == [2.0, 4.0, 8.0, 16.0]
    assert policy.next_delay(10) == 60.0

    with pytest.raises(ValueError):
        policy.next_delay(-1)


# --------------------------------------------------------------------- 分类边界


def test_is_retryable_recognizes_transient_failures() -> None:
    """瞬断识别：消息含 adb / device offline / connection reset by peer，或错误码命中。"""
    assert is_retryable(OSError("adb: device offline（设备离线）")) is True
    assert is_retryable(OSError("connection reset by peer")) is True
    assert is_retryable(OSError(errno.ECONNRESET, "连接被重置")) is True


def test_is_retryable_rejects_fatal_and_unknown() -> None:
    """致命（取消 / 契约 / 配置）与未知异常一律不可重试。"""
    assert is_retryable(ContractViolation("契约错误")) is False
    assert is_retryable(ConfigError("配置字段非法")) is False
    assert (
        is_retryable(
            FileNotFoundError(errno.ENOENT, "缺少配置文件", "G:/project_X/config/task.json")
        )
        is False
    )
    assert is_retryable(ValueError("普通业务错误")) is False
    assert is_retryable(Cancelled("用户停止")) is False
