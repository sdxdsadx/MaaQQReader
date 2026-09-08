"""识别层入口协议。

``PageObserver`` 负责「取一帧并提取全部特征证据」；它只观测、不判断状态。
判断由 :class:`~qqreader.page.recognizer.PageStateRecognizer` 完成。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from ..page.observation import PageObservation

if TYPE_CHECKING:  # pragma: no cover
    from .context import TaskContext


class PageObserver(Protocol):
    """页面观测器协议。"""

    def observe(self, context: "TaskContext", *, deep: bool = False) -> PageObservation:
        """抓取当前页面并提取多特征证据（模板/OCR/方向/App/结构）。

        ``deep=True`` 表示「常规特征不足，请追加证据」：识别适配器应补充
        次级模板（模板 B）、备用 OCR 区域/规则、结构探测等，并把结果合并进
        同一个 :class:`PageObservation`。它是 AGENTS.md §3.6「模板 A 找不到 →
        尝试模板 B / OCR / 页面特征」在观测层的落点。

        实现必须始终接受 ``deep`` 关键字参数；默认 ``False`` 表示只做常规观测。
        """
