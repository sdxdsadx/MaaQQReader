"""本轮 DirectReadingFlow: ReadingAlreadyInPage → Wait → Exit 全链核验 + 计时确认。"""
import re

log = open(r"G:\project_X\runtime\logs\maafw.log", encoding="utf-8", errors="replace").read()
events = []
for line in log.splitlines():
    m = re.search(r"\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\.(\d+)\]", line)
    if not m:
        continue
    ts = m.group(1)
    if "ReadingAlreadyInPage" in line and ("Recognition" in line or "enter" in line):
        events.append((ts, "ReadingAlreadyInPage 识别/进入"))
    if "ReadingWaitOneMinute" in line and "Node.Action.Starting" in line:
        events.append((ts, "ReadingWaitOneMinute 计时开始(post_delay=60000)"))
    if "ReadingWaitOneMinute" in line and ("Node.Action.Succeeded" in line or "node done" in line):
        events.append((ts, "ReadingWaitOneMinute 计时结束"))
    if "ReadingExitAfterTimer" in line and "Node.Action.Succeeded" in line:
        events.append((ts, "ReadingExitAfterTimer 按 BACK 退出"))
    if '"entry":"DirectReadingFlow"' in line and "task end" in line:
        events.append((ts, "任务结束"))
for ts, e in events[-10:]:
    print(ts, "|", e)
