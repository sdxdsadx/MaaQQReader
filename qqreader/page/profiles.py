"""默认页面状态定义（多特征）。

这些定义是**初始逻辑配置**，不是已实机校准的资源：

* 逻辑键来自旧工程 pipeline 的 OCR ``expected``（静态审计，见
  :mod:`qqreader.page.feature_keys`）；
* 真实模板、ROI、阈值必须在实际设备上重新截图校准（AGENTS.md §3.10.3/4），
  该项工作属于 QQR-6 / QQR-14 / QQR-15。

``CAPTCHA`` 状态刻意使用较低的确认门槛（多条证据任意组合即可），因为
「漏检验证码后继续点击」的代价远高于「误判后进入等待人工」。任务侧还会
用更敏感的 ``captcha_condition`` 再做一次兜底检测。
"""

from __future__ import annotations

from typing import List, Tuple

from .feature_keys import DEFAULT_FEATURE_KEYS, FeatureKeys
from .features import FeatureKind, FeatureSpec, MatchMode
from .recognizer import StateDefinition
from .states import Orientation, PageState


def _text(
    kind: FeatureKind,
    key: str,
    *,
    values: Tuple[str, ...] = (),
    weight: float = 1.0,
    required: bool = False,
    mode: MatchMode = MatchMode.CONTAINS,
    description: str = "",
) -> FeatureSpec:
    return FeatureSpec(
        kind=kind,
        key=key,
        values=values,
        weight=weight,
        required=required,
        mode=mode,
        description=description,
    )


def _icon(key: str, *, weight: float = 1.0, required: bool = False, threshold: float = 0.8) -> FeatureSpec:
    return FeatureSpec(
        kind=FeatureKind.ICON,
        key=key,
        weight=weight,
        required=required,
        threshold=threshold,
        mode=MatchMode.MIN_SCORE,
    )


def _template(key: str, *, weight: float = 1.0, required: bool = False, threshold: float = 0.75) -> FeatureSpec:
    return FeatureSpec(
        kind=FeatureKind.TEMPLATE,
        key=key,
        weight=weight,
        required=required,
        threshold=threshold,
        mode=MatchMode.MIN_SCORE,
    )


def _structure(key: str, *, weight: float = 1.0, required: bool = False, threshold: float = 0.6) -> FeatureSpec:
    return FeatureSpec(
        kind=FeatureKind.STRUCTURE,
        key=key,
        weight=weight,
        required=required,
        threshold=threshold,
        mode=MatchMode.MIN_SCORE,
    )


def _app(package: str, *, weight: float = 1.0, required: bool = True) -> FeatureSpec:
    return FeatureSpec(
        kind=FeatureKind.CURRENT_APP,
        key=package,
        weight=weight,
        required=required,
        mode=MatchMode.EQUALS,
    )


def _orientation(
    orientation: Orientation,
    *,
    values: Tuple[str, ...] = (),
    weight: float = 0.3,
) -> FeatureSpec:
    return FeatureSpec(
        kind=FeatureKind.ORIENTATION,
        key=orientation.value,
        values=values,
        weight=weight,
        mode=MatchMode.EQUALS,
    )


def build_default_state_definitions(
    keys: FeatureKeys = DEFAULT_FEATURE_KEYS,
) -> Tuple[StateDefinition, ...]:
    """构造 AGENTS.md §3.2 要求的全部页面状态定义。"""
    any_orientation = (Orientation.PORTRAIT.value, Orientation.LANDSCAPE.value)

    game_features: List[FeatureSpec] = []
    if keys.game_package:
        game_features.append(_app(keys.game_package, required=False))
    game_features.extend(
        [
            _text(
                FeatureKind.OCR,
                keys.game_ocr_select_server,
                values=(keys.game_ocr_enter, keys.game_ocr_enter_alt),
                weight=1.5,
                mode=MatchMode.ONE_OF,
                description="游戏登录/选服页文案",
            ),
            _template(keys.game_login_button, weight=1.0),
            _structure(keys.game_loading_marker, weight=1.0),
            _orientation(Orientation.LANDSCAPE, values=(Orientation.PORTRAIT.value,), weight=0.3),
        ]
    )

    return (
        StateDefinition(
            state=PageState.HOME,
            features=(
                _app(keys.qq_reader_package),
                _icon(keys.home_nav_my, weight=1.0, required=True),
                _text(FeatureKind.OCR, keys.home_ocr_shelf, weight=1.0, mode=MatchMode.EQUALS),
                _text(FeatureKind.OCR, keys.home_ocr_mine, weight=0.5),
                _structure(keys.home_bottom_nav, weight=0.5),
                _orientation(Orientation.PORTRAIT, weight=0.3),
            ),
            min_score=0.4,
            min_matched=3,
            description="QQ 阅读主页/书架：可预测的公共起点",
        ),
        StateDefinition(
            state=PageState.REWARD_HOME,
            features=(
                _app(keys.qq_reader_package),
                _text(
                    FeatureKind.OCR,
                    keys.reward_ocr_ad_banner,
                    values=(keys.reward_ocr_game_banner,),
                    weight=1.5,
                    mode=MatchMode.ONE_OF,
                    description="奖励页专属任务文案",
                ),
                _icon(keys.reward_header, weight=1.0),
                _structure(keys.reward_bottom_nav, weight=0.5),
                _orientation(Orientation.PORTRAIT, weight=0.3),
            ),
            min_score=0.4,
            min_matched=2,
            description="奖励页：看小视频领好礼 / 玩游戏领赠币",
        ),
        StateDefinition(
            state=PageState.AD_PLAYING,
            features=(
                _text(
                    FeatureKind.OCR,
                    keys.ad_ocr_countdown,
                    values=(keys.ad_ocr_skip, keys.ad_ocr_close),
                    weight=1.0,
                    mode=MatchMode.ONE_OF,
                ),
                _icon(keys.ad_skip, weight=1.0),
                _structure(keys.ad_video_surface, weight=1.0),
            ),
            min_score=0.4,
            min_matched=2,
            description="广告播放中：倒计时 / 跳过 / 视频区域",
        ),
        StateDefinition(
            state=PageState.AD_RESULT,
            features=(
                _text(
                    FeatureKind.OCR,
                    keys.ad_ocr_issued,
                    values=(keys.ad_ocr_coupon,),
                    weight=1.5,
                    mode=MatchMode.ONE_OF,
                ),
                _icon(keys.ad_result_close, weight=1.0),
                _structure(keys.ad_video_surface, weight=0.5),
            ),
            min_score=0.4,
            min_matched=2,
            description="广告结果/关闭页：奖品已发放 / 优惠券",
        ),
        StateDefinition(
            state=PageState.CAPTCHA,
            features=(
                _structure(keys.captcha_overlay, weight=1.5, threshold=0.5),
                _icon(keys.captcha_prompt_icon, weight=1.0),
                _template(keys.captcha_slider_track, weight=1.0, threshold=0.7),
                _text(
                    FeatureKind.OCR,
                    keys.captcha_ocr_pick,
                    values=(keys.captcha_ocr_slider,),
                    weight=1.5,
                    mode=MatchMode.ONE_OF,
                ),
            ),
            min_score=0.3,
            min_matched=2,
            description="验证码：图片顺序点选 / 滑动验证（求解与确认见 QQR-9）",
        ),
        StateDefinition(
            state=PageState.GAME_LOADING,
            features=tuple(game_features),
            min_score=0.4,
            min_matched=2,
            description="游戏登录/加载页：点击选服 / 踏入仙途 / 进入游戏",
        ),
        StateDefinition(
            state=PageState.GAME_RUNNING,
            features=(
                _structure(keys.game_hud, weight=1.5),
                _text(FeatureKind.OCR, keys.game_ocr_active, weight=1.0),
                _orientation(Orientation.LANDSCAPE, values=any_orientation, weight=0.3),
            ),
            min_score=0.4,
            min_matched=2,
            description="游戏运行中：HUD / 领币悬浮（横竖屏均兼容）",
        ),
        StateDefinition(
            state=PageState.GAME_RESULT,
            features=(
                _text(FeatureKind.OCR, keys.game_ocr_exit, weight=1.5),
                _template(keys.game_exit_dialog, weight=1.0, threshold=0.7),
                _icon(keys.game_exit_menu, weight=0.5),
            ),
            min_score=0.4,
            min_matched=2,
            description="游戏退出/结算页",
        ),
    )
