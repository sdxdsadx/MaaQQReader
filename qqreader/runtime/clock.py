"""时钟与取消令牌。

超时和取消语义必须可测试，因此核心只依赖 ``Clock`` 抽象：

* ``RealClock`` 用 ``time.monotonic``，等待时以短间隔轮询取消令牌，
  保证取消能及时打断 sleep。
* ``FakeClock`` 让单元测试精确推进时间，无需真的等待。
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Protocol

from ..errors import Cancelled

# RealClock 等待取消令牌时的轮询间隔（秒）。
_POLL_INTERVAL = 0.05


class CancellationToken:
    """可跨线程传递的取消信号。

    取消是**协作式**的：调用方在安全点调用 :meth:`throw_if_cancelled`，
    或在等待时使用 :meth:`wait`。
    """

    __slots__ = ("_event", "_reason")

    def __init__(self) -> None:
        self._event = threading.Event()
        self._reason: Optional[str] = None

    @property
    def is_cancelled(self) -> bool:
        return self._event.is_set()

    @property
    def reason(self) -> Optional[str]:
        return self._reason

    def cancel(self, reason: str = "cancelled") -> None:
        """请求取消；重复调用不会覆盖第一次的原因。"""
        if not self._event.is_set():
            self._reason = reason
            self._event.set()

    def throw_if_cancelled(self) -> None:
        if self._event.is_set():
            raise Cancelled(self._reason or "cancelled")

    def wait(self, timeout: float) -> bool:
        """等待至多 ``timeout`` 秒；被取消时立即返回 True。"""
        return self._event.wait(timeout)


class Clock(Protocol):
    """时间抽象。"""

    def now(self) -> float:
        """单调递增的秒数。"""

    def sleep(self, seconds: float, token: CancellationToken) -> None:
        """睡眠 ``seconds`` 秒；取消时抛出 :class:`Cancelled`。"""


class RealClock:
    """真实时钟。"""

    def now(self) -> float:
        return time.monotonic()

    def sleep(self, seconds: float, token: CancellationToken) -> None:
        if seconds <= 0:
            token.throw_if_cancelled()
            return
        deadline = self.now() + seconds
        while True:
            token.throw_if_cancelled()
            remaining = deadline - self.now()
            if remaining <= 0:
                return
            token.wait(min(remaining, _POLL_INTERVAL))


@dataclass
class FakeClock:
    """确定性时钟，用于单元测试。

    ``sleep`` 会直接推进 ``now`` 并记录睡眠时长；``on_sleep`` 回调可用于
    在指定睡眠次数时注入取消或其他副作用。
    """

    _now: float = 0.0
    sleeps: List[float] = field(default_factory=list)
    on_sleep: Optional[Callable[[int, float], None]] = None

    def now(self) -> float:
        return self._now

    def advance(self, seconds: float) -> None:
        """直接推进时间（不经过 sleep）。"""
        if seconds < 0:
            raise ValueError("seconds must be >= 0")
        self._now += seconds

    def sleep(self, seconds: float, token: CancellationToken) -> None:
        token.throw_if_cancelled()
        if seconds < 0:
            raise ValueError("seconds must be >= 0")
        self.sleeps.append(seconds)
        index = len(self.sleeps) - 1
        if self.on_sleep is not None:
            self.on_sleep(index, seconds)
        self._now += seconds
        token.throw_if_cancelled()
