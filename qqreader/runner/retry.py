"""运行期瞬断容错原语：可重试错误分类与指数退避（QQR-36 / issue #8）。

``scripts/run_task.py`` 在 adb 断连、设备离线、OCR 链路 RST 等瞬断下必须
「自动退避重试、每次重试可观测、耗尽后优雅失败」。本模块只提供这套原语，
不负责进程退出码映射：

* :func:`is_retryable` 判定异常是否属于可重试的瞬断；
* :class:`BackoffPolicy` 提供指数退避参数与 :meth:`~BackoffPolicy.next_delay`；
* :func:`run_with_retry` 按退避重试 ``func``，重试耗尽抛
  :class:`RetryExhaustedError`。

重要边界：

* **只有明确可识别的瞬断才重试**；未知异常一律视为致命，宁可快失败，
  也不在不确定的错误上反复空转。
* 取消（``Cancelled``）、契约错误（``ContractViolation``）、配置错误
  （``ConfigError`` / 配置文件缺失）绝不重试，立即向上抛出。
* 「重试耗尽」≠「致命错误」：前者抛 :class:`RetryExhaustedError`（携带
  总尝试次数与最后错误），后者原样抛出；调用方据此区分处理。
"""

from __future__ import annotations

import errno
import re
import time
from dataclasses import dataclass
from typing import Callable, FrozenSet, Optional, Pattern, Tuple, TypeVar

from ..config.errors import ConfigError
from ..errors import Cancelled, ContractViolation, QqReaderError
from ..runtime.clock import CancellationToken, Clock

#: 异常描述（小写后）出现任一子串即视为可重试的瞬断。
RETRYABLE_KEYWORDS: Tuple[str, ...] = (
    "connection reset",
    "connection aborted",
    "connection refused",
    "connection closed",
    "reset by peer",
    "broken pipe",
    "forcibly closed",
    "device offline",
    "device disconnected",
    "device not found",
    "device unauthorized",
    "still connecting",
    # adb 链路报错的具体文案太多，兜底按瞬断处理；
    # 配置类问题应由调用方以 ConfigError/ContractViolation 抛出（见 FATAL_TYPES）。
    "adb",
    "timed out",
    "timeout",
)

#: 异常类型名（小写后）出现任一子串即视为可重试的瞬断。
RETRYABLE_TYPE_KEYWORDS: Tuple[str, ...] = (
    "reset",
    "timeout",
    "disconnect",
    "offline",
    "unreachable",
    "connectionerror",
    "connectionabort",
    "connectionrefused",
)


def _known_errnos(*names: str) -> FrozenSet[int]:
    values = []
    for name in names:
        value = getattr(errno, name, None)
        if isinstance(value, int):
            values.append(value)
    return frozenset(values)


#: 可重试的系统错误码：连接被重置/中断/拒绝、管道断裂、超时、对端不可达、暂时不可用。
RETRYABLE_ERRNOS: FrozenSet[int] = _known_errnos(
    "ECONNRESET",
    "ECONNABORTED",
    "ECONNREFUSED",
    "EPIPE",
    "ETIMEDOUT",
    "EHOSTUNREACH",
    "ENETUNREACH",
    "ENETDOWN",
    "EHOSTDOWN",
    "EAGAIN",
)

#: Windows 原生错误码兜底：WSAECONNABORTED / WSAECONNRESET / WSAETIMEDOUT。
_RETRYABLE_WINERRORS: FrozenSet[int] = frozenset((10053, 10054, 10060))

#: 「RST」单独成词才算瞬断。不用 ``\b``：在 Unicode 模式下中文也算单词字符，
#: 「发生RST断开」会被误判为无边界；这里用 ASCII 字母做边界。
_RETRYABLE_PATTERNS: Tuple[Pattern[str], ...] = (
    re.compile(r"(?<![a-z])rst(?![a-z])"),
)

#: 明确致命的异常类型：绝不重试，立即向上抛出。
FATAL_TYPES: Tuple[type, ...] = (Cancelled, ContractViolation, ConfigError)

_CONFIG_PATH_HINTS: Tuple[str, ...] = ("config", "settings")
_CONFIG_PATH_SUFFIXES: Tuple[str, ...] = (
    ".json",
    ".toml",
    ".ini",
    ".cfg",
    ".conf",
    ".yaml",
    ".yml",
)


def _looks_like_config_error(exc: FileNotFoundError) -> bool:
    """``FileNotFoundError`` 的路径是否像配置文件（缺失即致命，不重试）。"""
    candidates = [getattr(exc, "filename", None)]
    candidates.extend(exc.args)
    for candidate in candidates:
        if not candidate:
            continue
        lowered = str(candidate).lower().replace("\\", "/")
        if any(hint in lowered for hint in _CONFIG_PATH_HINTS):
            return True
        if lowered.endswith(_CONFIG_PATH_SUFFIXES):
            return True
    return False


def is_retryable(exc: BaseException) -> bool:
    """判断异常是否属于「可重试的瞬断」。

    判定顺序（先致命、后瞬断，避免把致命错误误判成瞬断）：

    1. :data:`FATAL_TYPES`（取消 / 契约错误 / 配置错误）→ 不可重试；
    2. 配置文件缺失（``FileNotFoundError`` 且路径像配置）→ 不可重试；
    3. ``OSError`` 错误码命中连接重置 / 超时 / 不可达等瞬断码 → 可重试；
    4. 异常类型名或描述命中 adb 断连 / 设备离线 / connection reset / RST /
       timeout 等关键词 → 可重试。

    其余一律判为致命：宁可快失败，也不在未知错误上空转。
    """
    if isinstance(exc, FATAL_TYPES):
        return False
    if isinstance(exc, FileNotFoundError) and _looks_like_config_error(exc):
        return False
    if isinstance(exc, OSError) and getattr(exc, "errno", None) in RETRYABLE_ERRNOS:
        return True
    if getattr(exc, "winerror", None) in _RETRYABLE_WINERRORS:
        return True
    type_name = type(exc).__name__.lower()
    if any(keyword in type_name for keyword in RETRYABLE_TYPE_KEYWORDS):
        return True
    message = str(exc).lower()
    if any(keyword in message for keyword in RETRYABLE_KEYWORDS):
        return True
    return any(pattern.search(message) for pattern in _RETRYABLE_PATTERNS)


@dataclass(frozen=True)
class BackoffPolicy:
    """指数退避策略。

    第 ``attempt`` 次重试（从 0 开始）前等待
    ``base_delay * factor ** attempt`` 秒，并以 ``max_delay`` 截断。
    ``max_retries`` 是初始尝试失败后允许的额外尝试次数；默认 3 次，
    即总共最多尝试 4 次。
    """

    base_delay: float = 2.0
    factor: float = 2.0
    max_delay: float = 60.0
    max_retries: int = 3

    def __post_init__(self) -> None:
        if self.base_delay < 0:
            raise ContractViolation("base_delay 必须 >= 0")
        if self.factor < 1:
            raise ContractViolation("factor 必须 >= 1")
        if self.max_delay < 0:
            raise ContractViolation("max_delay 必须 >= 0")
        if self.max_retries < 0:
            raise ContractViolation("max_retries 必须 >= 0")

    def next_delay(self, attempt: int) -> float:
        """第 ``attempt`` 次重试（从 0 开始）前的等待秒数。"""
        if attempt < 0:
            raise ValueError("attempt 不能为负")
        return min(self.base_delay * (self.factor ** attempt), self.max_delay)


class RetryExhaustedError(QqReaderError):
    """可重试错误在退避重试耗尽后仍未成功（≠ 致命错误）。"""

    def __init__(self, attempts: int, last_error: BaseException) -> None:
        message = (
            f"重试耗尽：共尝试 {attempts} 次仍失败，"
            f"最后错误 {type(last_error).__name__}: {last_error}"
        )
        super().__init__(message)
        #: 总尝试次数（含初始尝试）。
        self.attempts = attempts
        #: 最后一次失败的异常。
        self.last_error = last_error


T = TypeVar("T")


def run_with_retry(
    func: Callable[[], T],
    policy: Optional[BackoffPolicy] = None,
    *,
    log: Optional[Callable[[str], None]] = None,
    clock: Optional[Clock] = None,
    token: Optional[CancellationToken] = None,
) -> T:
    """执行 ``func``：可重试错误退避重试，致命错误立即原样抛出。

    成功时返回 ``func`` 的结果；每次重试前通过 ``log`` 输出
    「第 N 次重试 / 原因 / 等待秒数」。重试耗尽（初始尝试 + ``max_retries``
    次重试全部失败）抛 :class:`RetryExhaustedError`，调用方据此把
    「瞬断重试耗尽」与「致命错误」区分开。

    ``clock`` / ``token`` 缺省时退化为 ``time.sleep``；注入
    :class:`~qqreader.runtime.clock.Clock` 后单测可确定性推进退避时间。
    """
    policy = policy or BackoffPolicy()
    attempts = 0
    retries = 0
    while True:
        attempts += 1
        try:
            return func()
        except Exception as exc:  # 只捕获 Exception：键盘中断/退出必须立即穿透
            if not is_retryable(exc):
                raise
            if retries >= policy.max_retries:
                raise RetryExhaustedError(attempts=attempts, last_error=exc) from exc
            delay = policy.next_delay(retries)
            retries += 1
            if log is not None:
                log(
                    f"第 {retries} 次重试 / 原因: {type(exc).__name__}: {exc} "
                    f"/ 等待 {delay:g} 秒"
                )
            _sleep_backoff(delay, clock, token)


def _sleep_backoff(
    seconds: float,
    clock: Optional[Clock],
    token: Optional[CancellationToken],
) -> None:
    """退避等待；优先使用注入的 clock（可测试），否则退回 ``time.sleep``。"""
    if clock is not None:
        clock.sleep(seconds, token if token is not None else CancellationToken())
        return
    if token is not None:
        token.throw_if_cancelled()
    if seconds > 0:
        time.sleep(seconds)
