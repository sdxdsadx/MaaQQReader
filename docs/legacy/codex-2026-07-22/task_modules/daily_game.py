TASK_ID = "daily_game"
TASK_NAME = "每日游戏"
DESCRIPTION = "进入赠币任务页，点击游戏中心轮播图进入任意游戏，计时后退出并返回书架。"
DEFAULT_MINUTES = 25
POST_DELAY_SECONDS = 3


def run(core, minutes=25, stop_event=None) -> None:
    core.daily_game(minutes, stop_event)
