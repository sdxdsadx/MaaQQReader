"""QQReader 异常类型。

这些异常是**控制流信号**，不是任务失败结论：

* ``Cancelled`` 由取消令牌触发，任务结果是 ``CANCELLED``，不是 ``FAILED``。
* ``StateNotConfirmed`` 表示页面状态未确认（只能重新判断），
  绝不能据此推导「目标不存在」或「任务失败」。
* ``ContractViolation`` 表示契约/配置本身写错，属于开发期错误。
"""

from __future__ import annotations


class QqReaderError(Exception):
    """项目内所有异常的基类。"""


class Cancelled(QqReaderError):
    """取消请求已触发。"""

    def __init__(self, reason: str = "cancelled") -> None:
        super().__init__(reason)
        self.reason = reason


class StateNotConfirmed(QqReaderError):
    """页面状态未达到确认阈值。

    语义：当前观测不足以确认任何页面状态，**只允许重新判断**。
    调用方不得把本异常解释为「目标不存在」或「任务失败」。
    """

    def __init__(self, reason: str = "state not confirmed") -> None:
        super().__init__(reason)
        self.reason = reason


class ContractViolation(QqReaderError):
    """任务契约或配置违反约束（开发期错误）。"""
