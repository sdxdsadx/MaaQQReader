"""一次页面观测的原始证据。

``PageObservation`` 只承载「看到了什么」，不做任何状态推断；状态推断由
:class:`~qqreader.page.recognizer.PageStateRecognizer` 完成。把两者分开，
是为了让识别层可以独立替换（模板、OCR、结构特征）而不影响状态机。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Optional, Tuple

from .states import Orientation


@dataclass(frozen=True)
class PageObservation:
    """某一帧的原始观测证据。"""

    current_app: Optional[str] = None
    orientation: Orientation = Orientation.UNKNOWN
    title: Optional[str] = None
    ocr_texts: Tuple[str, ...] = ()
    icons: Mapping[str, float] = field(default_factory=dict)
    templates: Mapping[str, float] = field(default_factory=dict)
    structure: Mapping[str, float] = field(default_factory=dict)
    #: ADB/设备是否可达；False 属于致命错误（无法靠点击恢复）。
    device_online: bool = True
    #: 目标 App 是否已安装；None 表示未知，False 属于致命错误。
    app_installed: Optional[bool] = None
    captured_at: Optional[float] = None
    screenshot_path: Optional[str] = None

    @classmethod
    def empty(cls) -> "PageObservation":
        return cls()

    def text_blob(self) -> str:
        """把标题与 OCR 文本拼成一个便于日志/断言查看的字符串。"""
        parts = [p for p in (self.title,) + tuple(self.ocr_texts) if p]
        return " | ".join(parts)

    def summary(self) -> str:
        return (
            f"app={self.current_app!r} orientation={self.orientation.value} "
            f"title={self.title!r} ocr={list(self.ocr_texts)!r} "
            f"icons={dict(self.icons)!r} templates={dict(self.templates)!r} "
            f"structure={dict(self.structure)!r}"
        )
