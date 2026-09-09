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

from typing import Tuple

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


def _ladder(
    primary: FeatureSpec,
    *fallbacks: FeatureSpec,
    weight: float = 1.0,
    required: bool = True,
    description: str = "",
) -> FeatureSpec:
    """把主特征 + §3.6 降级链封装成一条逻辑特征。

    主特征（模板 A）失败时，``match_feature`` 会按顺序尝试模板 B / OCR /
    页面结构等备选；任一命中即认为该逻辑特征成立。这样「模板 A 失效但页面
    确实存在」不会再因为单张模板匹配失败而直接判成 UNKNOWN。
    """
    return FeatureSpec(
        kind=primary.kind,
        key=primary.key,
        values=primary.values,
        weight=weight,
        required=required,
        threshold=primary.threshold,
        mode=primary.mode,
        description=description,
        fallbacks=tuple(fallbacks),
    )


def build_default_state_definitions(
    keys: FeatureKeys = DEFAULT_FEATURE_KEYS,
) -> Tuple[StateDefinition, ...]:
    """构造 AGENTS.md §3.2 要求的全部页面状态定义。

    广告与游戏的 6 个关键页面都使用「逻辑特征 + §3.6 降级链」：
    主模板/主 OCR 失败时，自动尝试模板 B / OCR / 页面结构；任一备选命中
    即可让该逻辑特征成立，并由其余特征（App / 方向 / 结构）做交叉确认。
    """
    any_orientation = (Orientation.PORTRAIT.value, Orientation.LANDSCAPE.value)
    game_app = _app(keys.game_package or keys.qq_reader_package, required=False)

    return (
        StateDefinition(
            state=PageState.HOME,
            features=(
                _app(keys.qq_reader_package),
                _ladder(
                    _icon(keys.home_nav_my, weight=1.0),
                    _text(
                        FeatureKind.OCR,
                        keys.home_ocr_shelf,
                        weight=1.0,
                        mode=MatchMode.EQUALS,
                    ),
                    _text(FeatureKind.OCR, keys.home_ocr_mine, weight=0.5),
                    _structure(keys.home_bottom_nav, weight=0.5),
                    weight=1.5,
                    required=True,
                    description="主页身份：底部「我的」/ 书架 / 底部导航结构",
                ),
                _orientation(Orientation.PORTRAIT, weight=0.3),
            ),
            min_score=0.4,
            min_matched=2,
            description="QQ 阅读主页/书架：可预测的公共起点",
        ),
        StateDefinition(
            state=PageState.REWARD_HOME,
            features=(
                _app(keys.qq_reader_package),
                _ladder(
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
                    weight=1.5,
                    required=True,
                    description="奖励页身份：广告/游戏任务文案 / 标题栏 / 底部结构",
                ),
                _orientation(Orientation.PORTRAIT, weight=0.3),
            ),
            min_score=0.4,
            min_matched=2,
            description="奖励页：看小视频领好礼 / 玩游戏领赠币",
        ),
        StateDefinition(
            state=PageState.AD_PLAYING,
            features=(
                _app(keys.qq_reader_package, required=False),
                _ladder(
                    _text(
                        FeatureKind.OCR,
                        keys.ad_ocr_countdown,
                        values=(keys.ad_ocr_skip, keys.ad_ocr_close),
                        weight=1.5,
                        mode=MatchMode.ONE_OF,
                    ),
                    _icon(keys.ad_skip, weight=1.0),
                    _structure(keys.ad_video_surface, weight=1.0),
                    weight=1.5,
                    required=True,
                    description="广告播放身份：倒计时/跳过/关闭文案 / 跳过图标 / 视频区域",
                ),
                _orientation(
                    Orientation.PORTRAIT,
                    values=any_orientation,
                    weight=0.3,
                ),
            ),
            min_score=0.4,
            min_matched=2,
            description="广告播放中：倒计时 / 跳过 / 视频区域",
        ),
        StateDefinition(
            state=PageState.AD_RESULT,
            features=(
                _app(keys.qq_reader_package, required=False),
                _ladder(
                    _text(
                        FeatureKind.OCR,
                        keys.ad_ocr_issued,
                        values=(keys.ad_ocr_coupon,),
                        weight=1.5,
                        mode=MatchMode.ONE_OF,
                    ),
                    _icon(keys.ad_result_close, weight=1.0),
                    _structure(keys.ad_video_surface, weight=0.5),
                    weight=1.5,
                    required=True,
                    description="广告结果身份：奖品已发放/优惠券 / 结果页关闭 / 视频结构",
                ),
                _orientation(
                    Orientation.PORTRAIT,
                    values=any_orientation,
                    weight=0.3,
                ),
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
            state=PageState.GAME_ENTRY,
            features=(
                game_app,
                # 「去玩游戏」是本状态最强的唯一证据；作为 required 主特征。
                _text(
                    FeatureKind.OCR,
                    keys.game_ocr_go_play,
                    weight=2.0,
                    required=True,
                    mode=MatchMode.CONTAINS,
                    description="去玩游戏按钮（旧 pipeline GameFindPlayButton）",
                ),
                # 奖励页游戏卡文案是上下文证据；与 REWARD_HOME 同时命中时，
                # GAME_ENTRY 的 matched_count 更高，优先选中本状态。
                _text(
                    FeatureKind.OCR,
                    keys.game_ocr_reward_entry,
                    weight=0.5,
                    mode=MatchMode.CONTAINS,
                ),
                _orientation(
                    Orientation.PORTRAIT,
                    values=any_orientation,
                    weight=0.3,
                ),
            ),
            min_score=0.4,
            min_matched=2,
            description="游戏任务页：点击「去玩游戏」进入游戏大厅/加载页",
        ),
        StateDefinition(
            state=PageState.GAME_HALL,
            features=(
                game_app,
                _text(
                    FeatureKind.OCR,
                    keys.game_ocr_hall_marker,
                    values=("今日必玩推荐", "新游", "活动", "排行", "分类", "在线玩"),
                    weight=2.0,
                    required=True,
                    mode=MatchMode.ONE_OF,
                    description="游戏大厅：精选大作 / 今日必玩推荐 / 排行 / 分类",
                ),
                _orientation(
                    Orientation.PORTRAIT,
                    values=any_orientation,
                    weight=0.3,
                ),
            ),
            min_score=0.4,
            min_matched=2,
            description="游戏大厅：点击轮播图进入任意游戏",
        ),
        StateDefinition(
            state=PageState.GAME_LOADING,
            features=(
                game_app,
                _ladder(
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
                    _text(
                        FeatureKind.OCR,
                        keys.game_ocr_hall_marker,
                        values=("今日必玩推荐", "新游", "活动", "排行", "分类"),
                        weight=1.0,
                        mode=MatchMode.ONE_OF,
                        description="游戏大厅推荐/分类文案",
                    ),
                    weight=1.5,
                    required=True,
                    description="游戏加载/大厅身份：点击选服/踏入仙途/进入游戏 / 登录页 / 精选大作等大厅文案",
                ),
                _orientation(
                    Orientation.LANDSCAPE,
                    values=any_orientation,
                    weight=0.3,
                ),
            ),
            min_score=0.4,
            min_matched=2,
            description="游戏登录/加载页：点击选服 / 踏入仙途 / 进入游戏",
        ),
        StateDefinition(
            state=PageState.GAME_RUNNING,
            features=(
                game_app,
                _ladder(
                    _structure(keys.game_hud, weight=1.5),
                    _text(FeatureKind.OCR, keys.game_ocr_active, weight=1.0),
                    weight=1.5,
                    required=True,
                    description="游戏运行身份：游戏内 HUD / 领币悬浮",
                ),
                _orientation(
                    Orientation.LANDSCAPE,
                    values=any_orientation,
                    weight=0.3,
                ),
            ),
            min_score=0.4,
            min_matched=2,
            description="游戏运行中：HUD / 领币悬浮（横竖屏均兼容）",
        ),
        StateDefinition(
            state=PageState.GAME_MENU,
            features=(
                game_app,
                _text(
                    FeatureKind.OCR,
                    keys.game_ocr_exit,
                    weight=2.0,
                    required=True,
                    mode=MatchMode.EQUALS,
                    description="悬浮窗延伸菜单：退出按钮",
                ),
                _text(
                    FeatureKind.OCR,
                    keys.game_ocr_active,
                    weight=0.5,
                    mode=MatchMode.CONTAINS,
                    description="仍能看到「领币」悬浮窗，确认是游戏内菜单",
                ),
                _orientation(
                    Orientation.PORTRAIT,
                    values=any_orientation,
                    weight=0.3,
                ),
            ),
            min_score=0.4,
            min_matched=2,
            description="游戏悬浮窗延伸菜单：点击「退出」",
        ),
        StateDefinition(
            state=PageState.GAME_EXIT_CONFIRM,
            features=(
                game_app,
                _text(
                    FeatureKind.OCR,
                    keys.game_ocr_close_game,
                    weight=2.0,
                    required=True,
                    mode=MatchMode.CONTAINS,
                    description="退出游戏确认弹窗：关闭游戏",
                ),
                _text(
                    FeatureKind.OCR,
                    keys.game_ocr_exit,
                    weight=0.5,
                    mode=MatchMode.CONTAINS,
                    description="退出确认弹窗上下文",
                ),
                _orientation(
                    Orientation.PORTRAIT,
                    values=any_orientation,
                    weight=0.3,
                ),
            ),
            min_score=0.4,
            min_matched=2,
            description="退出游戏确认弹窗：点击「关闭游戏」",
        ),
        StateDefinition(
            state=PageState.GAME_RESULT,
            features=(
                game_app,
                _ladder(
                    _text(FeatureKind.OCR, keys.game_ocr_exit, weight=1.5),
                    _template(keys.game_exit_dialog, weight=1.0, threshold=0.7),
                    _icon(keys.game_exit_menu, weight=0.5),
                    weight=1.5,
                    required=True,
                    description="游戏结果身份：退出文案 / 退出确认 / 悬浮菜单",
                ),
                _orientation(
                    Orientation.PORTRAIT,
                    values=any_orientation,
                    weight=0.3,
                ),
            ),
            min_score=0.4,
            min_matched=2,
            description="游戏退出/结算页",
        ),
    )
