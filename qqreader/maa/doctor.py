"""MaaFramework 自检：DLL / 资源 / 连接 / 截图 / OCR / 点击。

真机：``python -m qqreader.maa doctor --config configs/qqreader.yaml``
离线：``python -m qqreader.maa doctor --config ... --offline-image shot.png``
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional, Sequence, Tuple

from ..config import AppConfig
from .client import MaaClient, MaaClientError
from .factory import build_maa_client


@dataclass(frozen=True)
class DoctorCheck:
    name: str
    ok: bool
    detail: str = ""


@dataclass(frozen=True)
class DoctorReport:
    checks: Tuple[DoctorCheck, ...]

    @property
    def ok(self) -> bool:
        return all(check.ok for check in self.checks)

    def render(self) -> str:
        lines = ["MaaFramework 自检:"]
        for check in self.checks:
            mark = "[ok]  " if check.ok else "[fail]"
            lines.append(f"  {mark} {check.name}: {check.detail}")
        lines.append(f"结果: {'通过' if self.ok else '未通过'}")
        return "\n".join(lines)


def run_doctor(
    config: AppConfig,
    *,
    offline_images: Sequence[bytes] = (),
    offline_dir: Optional[Path] = None,
    clock: Any = None,
    client_factory: Optional[Callable[[], MaaClient]] = None,
) -> DoctorReport:
    """按顺序检查构建 / 连接 / 截图 / OCR / 点击；任何一步失败都记录原因。"""
    checks = []
    client = None
    use_custom = bool(offline_images) or offline_dir is not None
    try:
        if client_factory is not None:
            client = client_factory()
        else:
            client = build_maa_client(
                config,
                clock=clock,
                controller="custom" if use_custom else None,
                custom_images=offline_images,
                custom_dir=offline_dir,
            )
        checks.append(
            DoctorCheck(
                "构建客户端",
                True,
                f"controller={getattr(getattr(client, 'config', None), 'controller', 'custom')}",
            )
        )
        client.connect()
        checks.append(DoctorCheck("连接控制器", True, "连接成功"))
        screenshot = client.screencap()
        checks.append(
            DoctorCheck(
                "截图",
                True,
                f"{screenshot.width}x{screenshot.height}, {len(screenshot.data)} bytes",
            )
        )
        ocr = client.recognize("OCR", {}, screenshot)
        texts = ocr.all_texts()
        checks.append(
            DoctorCheck(
                "OCR",
                bool(texts),
                f"{len(texts)} 条文本"
                + (f"；示例: {', '.join(texts[:3])}" if texts else "；未识别到文本"),
            )
        )
        center = (screenshot.width // 2, screenshot.height // 2)
        clicked = client.click(center[0], center[1])
        checks.append(DoctorCheck("点击", clicked, f"中心 {center}"))
    except MaaClientError as exc:
        checks.append(DoctorCheck("Maa 调用", False, str(exc)))
    finally:
        if client is not None:
            client.close()
    return DoctorReport(tuple(checks))
