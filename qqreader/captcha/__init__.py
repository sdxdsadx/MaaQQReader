"""验证码层：检测后的阻塞、求解与求解后确认。"""

from .factory import build_default_captcha_guard
from .guard import (
    CaptchaGuard,
    CaptchaOutcome,
    CaptchaResolution,
    CaptchaSolver,
    ManualCaptchaGuard,
    SolveResult,
    VerifyingCaptchaGuard,
)
from .slide import SlideCaptchaSolver, detect_slide

__all__ = [
    "CaptchaGuard",
    "CaptchaOutcome",
    "CaptchaResolution",
    "CaptchaSolver",
    "ManualCaptchaGuard",
    "SlideCaptchaSolver",
    "SolveResult",
    "VerifyingCaptchaGuard",
    "build_default_captcha_guard",
    "detect_slide",
]
