"""默认任务装配。

把「广告 / 游戏」两个任务注册到同一个 :class:`TaskRegistry`；调度核心按
配置键取用，不需要认识任何任务名。
"""

from __future__ import annotations

from typing import Optional

from ..captcha.guard import CaptchaGuard
from ..config import AppConfig, ConfigError
from ..page.feature_keys import DEFAULT_FEATURE_KEYS, FeatureKeys
from ..page.profiles import build_default_state_definitions
from ..page.recognizer import PageStateRecognizer
from ..recovery.policy import EscalationPolicy
from ..runner.registry import TaskRegistry
from ..runtime.device import DeviceController
from ..runtime.observer import PageObserver
from .ad import (
    AD_TASK_NAME,
    DEFAULT_AD_TIMEOUT_SECONDS,
    build_ad_definition,
)
from .game import (
    DEFAULT_GAME_DURATION_SECONDS,
    DEFAULT_GAME_TIMEOUT_SECONDS,
    GAME_TASK_NAME,
    build_game_definition,
)


def build_default_registry(
    observer: PageObserver,
    device: DeviceController,
    *,
    keys: FeatureKeys = DEFAULT_FEATURE_KEYS,
    captcha_guard: Optional[CaptchaGuard] = None,
    ad_timeout_seconds: float = DEFAULT_AD_TIMEOUT_SECONDS,
    game_timeout_seconds: float = DEFAULT_GAME_TIMEOUT_SECONDS,
    game_duration_seconds: float = DEFAULT_GAME_DURATION_SECONDS,
    config: Optional[AppConfig] = None,
) -> TaskRegistry:
    """装配默认任务集合（广告 + 游戏）。

    传入 :class:`AppConfig` 时，用配置里的 ``enabled`` / ``timeout_seconds``
    覆盖默认值；未配置的任务沿用调用参数。自动验证码求解器尚未实现，因此
    ``captcha.solver != manual`` 且未注入 ``captcha_guard`` 时**直接报错**，
    而不是悄悄退回等待人工。
    """
    ad_enabled, ad_timeout = True, ad_timeout_seconds
    game_enabled, game_timeout = True, game_timeout_seconds
    if config is not None:
        ad_task = config.tasks.get(AD_TASK_NAME)
        if ad_task is not None:
            ad_enabled = ad_task.enabled
            if ad_task.timeout_seconds is not None:
                ad_timeout = ad_task.timeout_seconds
        game_task = config.tasks.get(GAME_TASK_NAME)
        if game_task is not None:
            game_enabled = game_task.enabled
            if game_task.timeout_seconds is not None:
                game_timeout = game_task.timeout_seconds
        if config.captcha.solver != "manual" and captcha_guard is None:
            raise ConfigError(
                f"captcha.solver={config.captcha.solver!r} 需要注入 captcha_guard；"
                "自动求解器尚未实现，当前只支持 manual（等待人工）"
            )

    recognizer = PageStateRecognizer(build_default_state_definitions(keys))
    recovery = EscalationPolicy()
    registry = TaskRegistry()
    if ad_enabled:
        registry.register(
            build_ad_definition(
                keys,
                observer,
                device,
                recovery,
                recognizer,
                timeout_seconds=ad_timeout,
                captcha_guard=captcha_guard,
            )
        )
    if game_enabled:
        registry.register(
            build_game_definition(
                keys,
                observer,
                device,
                recovery,
                recognizer,
                timeout_seconds=game_timeout,
                game_duration_seconds=game_duration_seconds,
                captcha_guard=captcha_guard,
            )
        )
    return registry


__all__ = [
    "AD_TASK_NAME",
    "GAME_TASK_NAME",
    "build_default_registry",
]
