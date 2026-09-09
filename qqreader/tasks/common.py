"""广告 / 游戏任务共享的条件与错误规则构造器。"""

from __future__ import annotations

from typing import Tuple

from ..contract.conditions import (
    Condition,
    any_of,
    feature,
    predicate,
    state_in,
)
from ..contract.contract import FatalErrorSpec, RecoverableErrorSpec
from ..page.feature_keys import FeatureKeys
from ..page.features import FeatureKind, FeatureSpec, MatchMode
from ..page.states import PageState


def feature_key(keys: FeatureKeys, value: str) -> str:
    """把 ``FeatureKeys`` 的字段值解析成适配器使用的逻辑字段名。

    动作计划应传字段名给 ``Action.tap_feature``；``MaaFeatureLocator`` 只
    认字段名，不认 OCR 文案/模板逻辑名。
    """
    return keys.logical_name(value)


def ocr(
    key: str,
    *,
    values: Tuple[str, ...] = (),
    mode: MatchMode = MatchMode.CONTAINS,
    weight: float = 1.0,
    description: str = "",
) -> FeatureSpec:
    return FeatureSpec(
        kind=FeatureKind.OCR,
        key=key,
        values=values,
        mode=mode,
        weight=weight,
        description=description,
    )


def template(key: str, *, threshold: float = 0.75) -> FeatureSpec:
    return FeatureSpec(
        kind=FeatureKind.TEMPLATE,
        key=key,
        threshold=threshold,
        mode=MatchMode.MIN_SCORE,
    )


def icon(key: str, *, threshold: float = 0.8) -> FeatureSpec:
    return FeatureSpec(
        kind=FeatureKind.ICON,
        key=key,
        threshold=threshold,
        mode=MatchMode.MIN_SCORE,
    )


def structure(key: str, *, threshold: float = 0.6) -> FeatureSpec:
    return FeatureSpec(
        kind=FeatureKind.STRUCTURE,
        key=key,
        threshold=threshold,
        mode=MatchMode.MIN_SCORE,
    )


def captcha_condition(keys: FeatureKeys) -> Condition:
    """高敏感度的验证码检测：任意一条验证码证据命中即触发。

    宁可误判后进入等待人工，也不允许漏检后继续点击（AGENTS.md §3.8）。
    """
    return any_of(
        state_in(PageState.CAPTCHA),
        feature(ocr(keys.captcha_ocr_pick)),
        feature(ocr(keys.captcha_ocr_slider, mode=MatchMode.REGEX)),
        feature(ocr(keys.captcha_ocr_title)),
        feature(template(keys.captcha_prompt_icon)),
        feature(template(keys.captcha_slider_track)),
        feature(structure(keys.captcha_overlay, threshold=0.5)),
    )


def health_fatal_errors(keys: FeatureKeys) -> Tuple[FatalErrorSpec, ...]:
    """设备/应用层面的致命错误：无法靠点击恢复。"""
    return (
        FatalErrorSpec(
            name="device_offline",
            when=predicate(
                lambda ctx: ctx.observation.device_online is False,
                "ADB 设备不可达",
            ),
            hint="检查模拟器是否启动、ADB 端口是否正确",
        ),
        FatalErrorSpec(
            name="app_missing",
            when=predicate(
                lambda ctx: ctx.observation.app_installed is False,
                f"应用未安装: {keys.qq_reader_package}",
            ),
            hint="确认 QQ 阅读已安装且包名正确",
        ),
    )


def popup_recoverable(keys: FeatureKeys) -> RecoverableErrorSpec:
    """普通弹窗遮挡：走恢复阶梯的关闭弹窗动作。"""
    return RecoverableErrorSpec(
        name="popup_blocking",
        when=any_of(
            feature(ocr(keys.popup_ocr_cancel)),
            feature(icon(keys.popup_close)),
        ),
        hint="关闭遮挡弹窗后重新判断页面",
    )


def wrong_page_recoverable(
    name: str, states: Tuple[PageState, ...], hint: str
) -> RecoverableErrorSpec:
    """误入其它任务页面：先恢复，绝不当作任务失败。"""
    return RecoverableErrorSpec(name=name, when=state_in(*states), hint=hint)
