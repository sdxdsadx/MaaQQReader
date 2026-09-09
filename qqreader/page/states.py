"""页面状态与运行状态的枚举定义。

``PageState`` 是**页面**处于哪里；``RunState`` 是**任务执行器**当前在做什么。
两者刻意分开：验证码是页面状态（``CAPTCHA``），而「等待人工」是运行状态
（``WAITING_FOR_HUMAN``），不会和页面状态混为一谈。
"""

from __future__ import annotations

from enum import Enum
from typing import Tuple


class PageState(str, Enum):
    """页面状态。

    AGENTS.md §3.2 要求至少包含下列 8 个状态；``HOME`` 是在此基础上额外
    增加的稳定公共起点——§3.4 要求广告任务从「QQ 阅读主页」开始，而
    ``start_condition`` 需要一个可预测的起点来表达这一点。
    ``GAME_ENTRY`` 是奖励页游戏卡点击后、「去玩游戏」按钮出现的中间页；
    它不属于规范明文要求的 8 个状态，但游戏流程必须显式经过它。
    """

    HOME = "HOME"
    REWARD_HOME = "REWARD_HOME"
    AD_PLAYING = "AD_PLAYING"
    AD_RESULT = "AD_RESULT"
    CAPTCHA = "CAPTCHA"
    GAME_ENTRY = "GAME_ENTRY"
    GAME_HALL = "GAME_HALL"
    GAME_LOADING = "GAME_LOADING"
    GAME_RUNNING = "GAME_RUNNING"
    GAME_MENU = "GAME_MENU"
    GAME_EXIT_CONFIRM = "GAME_EXIT_CONFIRM"
    GAME_RESULT = "GAME_RESULT"
    UNKNOWN = "UNKNOWN"

    @property
    def is_unknown(self) -> bool:
        return self is PageState.UNKNOWN


#: AGENTS.md §3.2 明文要求的状态集合。
REQUIRED_PAGE_STATES: Tuple[PageState, ...] = (
    PageState.REWARD_HOME,
    PageState.AD_PLAYING,
    PageState.AD_RESULT,
    PageState.CAPTCHA,
    PageState.GAME_LOADING,
    PageState.GAME_RUNNING,
    PageState.GAME_RESULT,
    PageState.UNKNOWN,
)


class Orientation(str, Enum):
    """屏幕方向。"""

    PORTRAIT = "PORTRAIT"
    LANDSCAPE = "LANDSCAPE"
    UNKNOWN = "UNKNOWN"


class RunState(str, Enum):
    """任务执行器的运行状态。"""

    IDLE = "IDLE"
    STARTING = "STARTING"            # 正在到达 start_condition 的公共起点
    PREPARING = "PREPARING"          # 正在满足 ready_condition
    RUNNING = "RUNNING"              # 正在向 success_condition 推进
    RECOVERING = "RECOVERING"        # 正在执行升级式恢复
    CAPTCHA = "CAPTCHA"              # 已检测到验证码，正常推进暂停
    WAITING_FOR_HUMAN = "WAITING_FOR_HUMAN"  # 自动求解失败，等待人工
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    TIMEOUT = "TIMEOUT"
    CANCELLED = "CANCELLED"


#: 终止态。
TERMINAL_RUN_STATES = frozenset(
    {
        RunState.SUCCEEDED,
        RunState.FAILED,
        RunState.TIMEOUT,
        RunState.CANCELLED,
        RunState.WAITING_FOR_HUMAN,
    }
)
