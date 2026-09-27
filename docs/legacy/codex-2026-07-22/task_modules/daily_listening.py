TASK_ID = "daily_listening"
TASK_NAME = "每日听书"
DESCRIPTION = "识别《全职法师》封面和 AI 朗读播放按钮。"
DEFAULT_MINUTES = 25
POST_DELAY_SECONDS = 3


def run(core, minutes=25, stop_event=None) -> None:
    core.daily_listening(minutes, stop_event)
