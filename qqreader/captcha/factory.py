"""验证码 guard 工厂：默认接入滑块求解器 + 求解后复核。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from .guard import CaptchaGuard, VerifyingCaptchaGuard
from .slide import SlideCaptchaSolver

if TYPE_CHECKING:  # pragma: no cover
    from ..page.recognizer import PageStateRecognizer
    from ..runtime.device import DeviceController
    from ..runtime.observer import PageObserver


def build_default_captcha_guard(
    *,
    observer: "PageObserver",
    device: "DeviceController",
    recognizer: "PageStateRecognizer",
    captcha_condition,
    max_attempts: int = 2,
) -> CaptchaGuard:
    """构造「滑动求解 → 复核消失 → 否则等待人工」的默认 guard。"""
    solver = SlideCaptchaSolver(observer=observer, device=device)
    return VerifyingCaptchaGuard(
        solver,
        observer,
        recognizer,
        captcha_condition,
        max_attempts=max_attempts,
    )
