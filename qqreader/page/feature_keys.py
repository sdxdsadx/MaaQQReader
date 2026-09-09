"""页面特征键（逻辑名）。

这里只放**逻辑键**，不放盘符、绝对路径或硬编码坐标。真实模板文件名、OCR
正则、ROI、阈值由识别适配器/配置提供，属于 QQR-6（多特征识别策略）与
QQR-14/15（任务接入）的调优范围。

默认值来自旧工程 ``assets/resource/pipeline/qq_reader_trial.json`` 的
OCR ``expected``（静态审计），仅作为**初始逻辑名**；按 AGENTS.md §3.10.3/4，
必须用实际设备重新截图校准后才能视为有效资源。
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from typing import Optional


@dataclass(frozen=True)
class FeatureKeys:
    """各页面状态的逻辑特征名。"""

    # --- App ---
    qq_reader_package: str = "com.qq.reader"
    #: 第三方小游戏包名；未确认前保持 None，状态定义会跳过当前 App 特征。
    game_package: Optional[str] = None

    # --- HOME（QQ 阅读主页/书架，公共起点）---
    home_ocr_shelf: str = "书架"
    home_ocr_mine: str = "我的"
    home_nav_my: str = "home.nav_my"                 # 固定图标：底部「我的」
    home_bottom_nav: str = "home.bottom_nav"         # 结构特征：底部导航
    home_reward_entry: str = "home.reward_entry"     # 主页/书架上的奖励页入口（模板逻辑名，待校准）
    #: 书架奖励入口 OCR；页面文案会变（如「本周阅读时长/领赠币」→
    #: 「再读7分钟领20赠币」），用正则兼容两种。
    home_ocr_reward_entry: str = r"本周阅读时长|再读\d+分钟领\d+赠币"

    # --- REWARD_HOME（奖励页）---
    reward_header: str = "reward.header"             # 固定图标：奖励页标题栏
    reward_bottom_nav: str = "reward.bottom_nav"     # 结构特征
    reward_ocr_granted: str = "今日已获赠币"
    reward_ocr_ad_banner: str = "看小视频领好礼"
    reward_ocr_game_banner: str = "玩游戏领赠币"
    reward_ocr_watch: str = "立即观看"
    #: 旧 pipeline `AdClickWatch` 的备选文案。
    reward_ocr_watch_alt: str = "看小视频再多领"
    #: 实际 OCR 可能只识别出「立」；作为按钮定位兜底。
    reward_ocr_watch_partial: str = "立"
    reward_ocr_done: str = "明日再来"

    # --- AD_PLAYING / AD_RESULT ---
    ad_video_surface: str = "ad.video_surface"       # 结构特征：视频播放区域
    ad_skip: str = "ad.skip"                         # 固定图标：跳过/关闭按钮
    ad_ocr_countdown: str = "广告"
    ad_ocr_skip: str = "跳过"
    ad_ocr_close: str = "关闭"
    ad_ocr_continue: str = "继续观看"
    #: 跳过广告时出现的「确定要退出吗?」弹窗按钮。
    ad_ocr_claim_after_exit: str = "去领取奖励"
    ad_ocr_force_exit: str = "坚持退出"
    #: 广告详情/浏览页文案；出现时点左上角 X 关闭，不进入详情。
    ad_ocr_offer: str = "了解详情"
    ad_ocr_offer_alt: str = "跳转详情页或第三方应用"
    ad_result_close: str = "ad.result_close"         # 固定图标：结果页关闭
    ad_ocr_issued: str = "奖品已发放"
    ad_ocr_coupon: str = "恭喜获得优惠券"
    ad_success_counter: str = "12/12"                # 唯一正常完成标志之一
    ad_success_done: str = "明日再来"
    #: 旧工程 AdDailyComplete 的正则（静态审计，待实机校准）。
    ad_success_regex: str = (
        r"(?:12\s*/\s*12)|(?:(?:看小视频|看视频).*(?:明日再来|已领取|已领))"
    )

    # --- CAPTCHA ---
    captcha_overlay: str = "captcha.overlay"         # 结构特征：验证码遮罩
    captcha_prompt_icon: str = "captcha.prompt_icon"  # 固定图标：顶部提示
    captcha_slider_track: str = "captcha.slider_track"  # 局部模板：滑块轨道
    captcha_ocr_pick: str = "请在下图依次点击"        # 图片顺序点选验证码
    captcha_ocr_title: str = "安全验证"              # 验证码页标题
    #: 滑动验证码文案；正则避免依赖单一版本。
    captcha_ocr_slider: str = "拖动下方滑块|拖动滑块|滑动验证|完成拼图"

    # --- GAME ---
    game_entry: str = "game.entry"                   # 奖励页/主页的游戏入口（模板逻辑名，待实机校准）
    #: 奖励页游戏卡 OCR；也是点击奖励页游戏入口的首选定位方式。
    game_ocr_reward_entry: str = "玩游戏领赠币"
    #: 奖励页游戏卡点击后出现的「去玩游戏」按钮（旧 pipeline GameFindPlayButton）。
    game_ocr_go_play: str = "去玩游戏"
    game_ocr_hall: str = "游戏大厅"
    #: 游戏大厅真实文案（旧 pipeline GameHallRetry）；「游戏大厅」标题不一定出现。
    game_ocr_hall_marker: str = "精选大作"
    #: 游戏大厅「在线玩」入口（QQR-20：下划一次后识别并点击）。
    game_ocr_online_play: str = "在线玩"
    game_loading_marker: str = "game.loading_marker"  # 结构特征：游戏登录页
    game_login_button: str = "game.login_button"      # 局部模板：登录按钮
    game_ocr_select_server: str = "点击选服"
    game_ocr_enter: str = "进入游戏"
    game_ocr_enter_alt: str = "踏入仙途"
    #: 部分小游戏登录页按钮文案（QQR-20 实测）。
    game_ocr_login_game: str = "登录游戏"
    #: 游戏中心页标题/标识。
    game_ocr_game_center: str = "游戏中心"
    #: 游戏协议勾选框文案；点击其左侧坐标切换同意。
    game_ocr_agreement: str = "我已详细阅读并同意"
    #: 游戏隐私/协议弹窗的「同意」按钮（进入部分小游戏时会弹出）。
    game_ocr_agree: str = "同意"
    #: 游戏隐私/协议弹窗的「拒绝」按钮（仅用于识别，不点击）。
    game_ocr_reject: str = "拒绝"
    game_hud: str = "game.hud"                       # 结构特征：游戏内 HUD
    game_ocr_active: str = "领币"
    game_exit_menu: str = "game.exit_menu"           # 固定图标：悬浮菜单
    game_ocr_exit: str = "退出"
    #: 部分小游戏退出弹窗的确认按钮文案。
    game_ocr_close_game: str = "关闭游戏"
    game_exit_dialog: str = "game.exit_dialog"       # 局部模板：退出确认
    #: 奖励页游戏赠币领取按钮；游戏时长满足后出现。
    game_ocr_claim: str = "立即领取"
    #: 旧工程「玩游戏领赠币 + 已领取/明日再来」完成判定（静态审计，待实机校准）。
    game_success_regex: str = r"玩游戏领赠币.*(?:已领取|明日再来)"

    # --- 通用弹窗 ---
    popup_close: str = "popup.close"
    popup_ocr_cancel: str = "取消"

    def logical_name(self, value: str) -> str:
        """把字段值（逻辑名或 OCR 文案）解析成适配器使用的字段名。

        ``FeatureCatalog`` 以 dataclass 字段名为键保存识别资源；动作计划若
        直接传字段值（例如 OCR 文案「去玩游戏」），定位器会查不到资源。
        本方法返回第一个值匹配的字段名，保证 ``Action.tap_feature`` 与
        ``MaaFeatureLocator`` 使用同一套逻辑键。
        """
        for field in fields(self):
            if getattr(self, field.name) == value:
                return field.name
        raise KeyError(f"没有值为 {value!r} 的特征键")


DEFAULT_FEATURE_KEYS = FeatureKeys()
