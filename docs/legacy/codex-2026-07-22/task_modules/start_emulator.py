TASK_ID = "start_emulator"
TASK_NAME = "启动 MuMu 模拟器"
DESCRIPTION = "连接或启动 MuMu，并校验 ADB 与 720×1280 分辨率。"
DEFAULT_MINUTES = 0
POST_DELAY_SECONDS = 10


def run(core, minutes=0, stop_event=None) -> None:
    core.ensure_emulator()

