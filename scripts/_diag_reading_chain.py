"""DirectReadingFlow SUCCESS（书已打开在正文页第34章）。
旧流程跑完就退出（不包含 1 分钟计时？——之前修好的 60s 计时链在
ReadingWaitOneMinute 节点）。查本轮是否执行了 WaitOneMinute：
抓本轮 timeline 全部节点名。"""
from pathlib import Path
import re

p = Path(r"G:\project_X\dev\debug\maafw.log")
rows = p.read_text(encoding="utf-8", errors="replace").splitlines()
starts = [i for i, r in enumerate(rows) if "MaaTaskerPostTask" in r and "DirectReadingFlow" in r]
seg = rows[starts[-1]:]
nodes = []
for r in seg:
    m = re.search(r"Node\.PipelineNode\.(?:Starting|Succeeded)\] .*?\"name\":\"(\w+)\"", r)
    if m:
        nodes.append((m.group(1), "S" if "Succeeded" in r else ">"))
seen = []
for n, st in nodes:
    seen.append(f"{n}{st}")
print("节点链:", " -> ".join(seen[-12:]))
print("总节点事件:", len(nodes))
# WaitOneMinute 相关
w = [r for r in seg if "WaitOneMinute" in r]
print("WaitOneMinute 事件:", len(w))
