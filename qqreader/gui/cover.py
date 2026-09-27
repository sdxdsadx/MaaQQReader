"""听书封面：从模拟器截图中框选封面并保存为 Maa 模板（纯逻辑，不依赖 Tkinter）。

模板匹配不做缩放，所以封面必须从 720×1280 的原始截图里按原尺寸裁出；
GUI 只是把截图缩小显示，框选坐标在这里换算回原图。
"""

from __future__ import annotations

import subprocess
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional, Sequence, Tuple

Box = Tuple[int, int, int, int]

#: 太小的框几乎必然误匹配；太大的框（接近整屏）不是封面。
MIN_COVER_SIDE = 24
MAX_COVER_AREA_RATIO = 0.5
COVER_DIR_NAME = "covers"


def display_scale(width: int, height: int, max_width: int, max_height: int) -> int:
    """整数缩小倍数（Tk PhotoImage.subsample 只接受整数）。"""
    if width <= 0 or height <= 0:
        raise ValueError("截图尺寸非法")
    scale = 1
    while width / scale > max_width or height / scale > max_height:
        scale += 1
    return scale


def crop_box(
    start: Tuple[float, float],
    end: Tuple[float, float],
    scale: int,
    size: Tuple[int, int],
) -> Box:
    """把显示坐标上的两个角点换算为原图 (x, y, w, h)，并裁到图内。"""
    width, height = size
    x0, x1 = sorted((start[0] * scale, end[0] * scale))
    y0, y1 = sorted((start[1] * scale, end[1] * scale))
    left = max(0, min(width, int(round(x0))))
    right = max(0, min(width, int(round(x1))))
    top = max(0, min(height, int(round(y0))))
    bottom = max(0, min(height, int(round(y1))))
    box = (left, top, right - left, bottom - top)
    validate_cover_box(box, size)
    return box


def validate_cover_box(box: Box, size: Tuple[int, int]) -> None:
    _x, _y, w, h = box
    if w < MIN_COVER_SIDE or h < MIN_COVER_SIDE:
        raise ValueError(f"框选区域太小（{w}×{h}），请框住整张封面")
    if w * h > size[0] * size[1] * MAX_COVER_AREA_RATIO:
        raise ValueError("框选区域太大，请只框住一本书的封面")


def _decode(png: bytes):
    import cv2  # type: ignore[import-not-found]
    import numpy as np  # type: ignore[import-not-found]

    image = cv2.imdecode(np.frombuffer(png, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("截图无法解码")
    return image


def image_size(png: bytes) -> Tuple[int, int]:
    image = _decode(png)
    return int(image.shape[1]), int(image.shape[0])


def crop_png(png: bytes, box: Box) -> bytes:
    """按原图坐标裁剪并重新编码为 PNG。"""
    import cv2  # type: ignore[import-not-found]

    image = _decode(png)
    x, y, w, h = box
    part = image[y : y + h, x : x + w]
    if part.size == 0:
        raise ValueError("裁剪区域为空")
    ok, encoded = cv2.imencode(".png", part)
    if not ok:
        raise ValueError("封面编码失败")
    return encoded.tobytes()


def save_cover(runtime_dir: Path, png: bytes, *, prefix: str = "audiobook_cover") -> Path:
    """保存到 ``runtime/covers/``（runtime 不进仓库）。"""
    directory = Path(runtime_dir) / COVER_DIR_NAME
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"{prefix}_{datetime.now():%Y%m%d_%H%M%S}.png"
    target.write_bytes(png)
    return target


def check_cover_file(path: Path, screen: Tuple[int, int] = (720, 1280)) -> str:
    """检查用户选的封面文件；返回问题说明，没问题返回空串。"""
    path = Path(path)
    if not path.is_file():
        return f"封面文件不存在: {path}"
    try:
        width, height = image_size(path.read_bytes())
    except (OSError, ValueError, ImportError) as exc:
        return f"封面文件无法读取: {exc}"
    if width < MIN_COVER_SIDE or height < MIN_COVER_SIDE:
        return f"封面太小（{width}×{height}）"
    if width > screen[0] or height > screen[1] or width * height > screen[0] * screen[1] * MAX_COVER_AREA_RATIO:
        return (
            f"封面尺寸 {width}×{height} 比书架上的封面大得多；模板匹配不缩放，"
            "请用「截取封面」从模拟器画面中框选"
        )
    return ""


Runner = Callable[..., "subprocess.CompletedProcess[bytes]"]


def capture_screen_png(
    adb_path: str,
    address: str,
    *,
    runner: Optional[Runner] = None,
    timeout: float = 20.0,
) -> bytes:
    """``adb exec-out screencap -p``；书架页不受 FLAG_SECURE 限制。"""
    run = runner or subprocess.run
    command: Sequence[str] = (adb_path, "-s", address, "exec-out", "screencap", "-p")
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    result = run(
        list(command),
        capture_output=True,
        timeout=timeout,
        check=False,
        creationflags=creationflags,
    )
    data = result.stdout or b""
    if result.returncode != 0 or not data.startswith(b"\x89PNG"):
        detail = (result.stderr or b"").decode("utf-8", "replace").strip()
        raise RuntimeError(f"截图失败（exit={result.returncode}）{detail}")
    return data
