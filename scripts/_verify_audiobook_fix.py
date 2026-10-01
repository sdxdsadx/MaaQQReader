"""听书链核验: AlreadyPlaying→计时→暂停收尾→任务结束。"""
import re

log = open(r"G:\project_X\runtime\logs\maafw.log", encoding="utf-8", errors="replace").read()
events = []
for line in log.splitlines():
    m = re.search(r"\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})", line)
    if not m:
        continue
    ts = m.group(1)
    if "AudiobookAlreadyPlaying" in line and "enter" in line:
        events.append((ts, "AlreadyPlaying 进入"))
    if "AudiobookWaitOneMinute" in line and "Node.Action.Starting" in line:
        events.append((ts, "听书计时开始(post_delay=60000)"))
    if "AudiobookWaitOneMinute" in line and "node done" in line:
        events.append((ts, "听书计时结束"))
    if "AudiobookPauseAfterTrial" in line and "Succeeded" in line:
        events.append((ts, "暂停收尾完成"))
    if '"entry":"DailyAudiobookFlow"' in line and "task end" in line:
        events.append((ts, "任务结束"))
for ts, e in events[-8:]:
    print(ts, "|", e)
