"""验证码层：检测后的阻塞、求解与求解后确认。"""

from .guard import (
    CaptchaGuard,
    CaptchaOutcome,
    CaptchaResolution,
    CaptchaSolver,
    ManualCaptchaGuard,
    SolveResult,
    VerifyingCaptchaGuard,
)

__all__ = [
    "CaptchaGuard",
    "CaptchaOutcome",
    "CaptchaResolution",
    "CaptchaSolver",
    "ManualCaptchaGuard",
    "SolveResult",
    "VerifyingCaptchaGuard",
]
