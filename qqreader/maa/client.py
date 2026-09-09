"""MaaFramework 客户端抽象（协议 + 纯数据）。

真实实现见 :mod:`qqreader.maa.ctypes_client`；测试用假实现即可，因此
``device`` / ``observer`` / ``locator`` 的逻辑可以完全脱离真机验证。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Optional, Protocol, Sequence, Tuple

from ..errors import QqReaderError

Box = Tuple[int, int, int, int]


class MaaClientError(QqReaderError):
    """MaaFramework 调用失败（DLL 缺失、连接失败、截图/识别失败等）。"""


@dataclass(frozen=True)
class Screenshot:
    """一帧截图（默认保存为编码后的 PNG 字节）。"""

    data: bytes
    width: int
    height: int
    channels: int = 3
    captured_at: float = 0.0
    source: str = ""

    def __post_init__(self) -> None:
        if self.width <= 0 or self.height <= 0:
            raise MaaClientError(f"截图尺寸非法: {self.width}x{self.height}")
        if not self.data:
            raise MaaClientError("截图数据为空")

    @property
    def landscape(self) -> bool:
        return self.width > self.height

    @property
    def portrait(self) -> bool:
        return self.height > self.width

    def to_bgr(self):  # noqa: ANN201 - 返回 numpy.ndarray
        """解码为 OpenCV BGR 数组（需要 numpy + cv2，核心不强制依赖）。"""
        import cv2  # type: ignore[import-not-found]
        import numpy as np  # type: ignore[import-not-found]

        array = np.frombuffer(self.data, dtype=np.uint8)
        image = cv2.imdecode(array, cv2.IMREAD_COLOR)
        if image is None:
            raise MaaClientError("截图解码失败（不是有效图片）")
        return image

    def save(self, path: Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(self.data)
        return path


@dataclass(frozen=True)
class RecoResult:
    """一次 Maa 识别结果。"""

    reco_type: str
    hit: bool
    box: Optional[Box] = None
    detail: Mapping[str, Any] = field(default_factory=dict)
    text: Optional[str] = None
    score: Optional[float] = None

    @property
    def center(self) -> Optional[Tuple[int, int]]:
        if self.box is None:
            return None
        x, y, w, h = self.box
        return x + w // 2, y + h // 2

    def all_texts(self) -> Tuple[str, ...]:
        """解析 OCR detail 中的全部文本（``all`` 数组）。"""
        raw = self.detail.get("all") if isinstance(self.detail, Mapping) else None
        if not isinstance(raw, Sequence):
            return ()
        texts = []
        for item in raw:
            if isinstance(item, Mapping) and item.get("text"):
                texts.append(str(item["text"]))
        return tuple(texts)

    def text_boxes(self) -> Tuple[Tuple[str, Box], ...]:
        raw = self.detail.get("all") if isinstance(self.detail, Mapping) else None
        if not isinstance(raw, Sequence):
            return ()
        result = []
        for item in raw:
            if not isinstance(item, Mapping):
                continue
            box = item.get("box")
            text = item.get("text")
            if text and isinstance(box, Sequence) and len(box) == 4:
                result.append((str(text), tuple(int(v) for v in box)))  # type: ignore[arg-type]
        return tuple(result)

    @classmethod
    def miss(cls, reco_type: str, reason: str = "") -> "RecoResult":
        return cls(reco_type=reco_type, hit=False, detail={"reason": reason})


class MaaClient(Protocol):
    """MaaFramework 最小能力集：截图 / 点击 / 识别。"""

    def connect(self) -> None:
        ...

    def close(self) -> None:
        ...

    def screencap(self) -> Screenshot:
        ...

    def click(self, x: int, y: int) -> bool:
        ...

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 300) -> bool:
        ...

    def click_key(self, keycode: int) -> bool:
        ...

    def start_app(self, package: str) -> bool:
        ...

    def stop_app(self, package: str) -> bool:
        ...

    def recognize(
        self, reco_type: str, params: Mapping[str, Any], screenshot: Screenshot
    ) -> RecoResult:
        ...
