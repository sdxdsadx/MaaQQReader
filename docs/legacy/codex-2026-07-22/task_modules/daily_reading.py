TASK_ID = "daily_reading"
TASK_NAME = "每日阅读（自动阅读）"
DESCRIPTION = "识别阅读用书、阅读设置和自动阅读按钮。"
DEFAULT_MINUTES = 25
POST_DELAY_SECONDS = 3


def run(core, minutes=25, stop_event=None) -> None:
    core.daily_reading(minutes, stop_event)
