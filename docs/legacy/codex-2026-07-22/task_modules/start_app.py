TASK_ID = "start_app"
TASK_NAME = "启动模拟器与 QQ 阅读"
DESCRIPTION = "连接或启动 MuMu，校验 720×1280，并打开 QQ 阅读。"
DEFAULT_MINUTES = 0


def run(core, minutes=0, stop_event=None) -> None:
    core.ensure_emulator()
    core.start_qqreader()
