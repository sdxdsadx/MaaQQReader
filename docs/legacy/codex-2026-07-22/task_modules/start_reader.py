TASK_ID = "start_reader"
TASK_NAME = "启动 QQ 阅读"
DESCRIPTION = "显式打开 QQ 阅读并通过封面识别确认已进入书架。"
DEFAULT_MINUTES = 0
POST_DELAY_SECONDS = 8


def run(core, minutes=0, stop_event=None) -> None:
    core.ensure_emulator()
    core.start_qqreader()
    core.ensure_bookshelf()

