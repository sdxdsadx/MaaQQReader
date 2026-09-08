"""具体任务层：广告 / 游戏的契约、动作计划与装配。"""

from .ad import (
    AD_TASK_NAME,
    DEFAULT_AD_TIMEOUT_SECONDS,
    build_ad_action_plan,
    build_ad_contract,
    build_ad_definition,
)
from .common import (
    captcha_condition,
    health_fatal_errors,
    popup_recoverable,
    wrong_page_recoverable,
)
from .defaults import build_default_registry
from .game import (
    DEFAULT_GAME_DURATION_SECONDS,
    DEFAULT_GAME_TIMEOUT_SECONDS,
    GAME_TASK_NAME,
    GameTaskAdapter,
    build_game_action_plan,
    build_game_contract,
    build_game_definition,
)
from .plan import (
    Action,
    ActionKind,
    PlannedTaskAdapter,
    StateActionPlan,
)

__all__ = [
    "AD_TASK_NAME",
    "Action",
    "ActionKind",
    "DEFAULT_AD_TIMEOUT_SECONDS",
    "DEFAULT_GAME_DURATION_SECONDS",
    "DEFAULT_GAME_TIMEOUT_SECONDS",
    "GAME_TASK_NAME",
    "GameTaskAdapter",
    "PlannedTaskAdapter",
    "StateActionPlan",
    "build_ad_action_plan",
    "build_ad_contract",
    "build_ad_definition",
    "build_default_registry",
    "build_game_action_plan",
    "build_game_contract",
    "build_game_definition",
    "captcha_condition",
    "health_fatal_errors",
    "popup_recoverable",
    "wrong_page_recoverable",
]
