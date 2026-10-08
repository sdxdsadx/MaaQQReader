"""这轮是「今日任务已完成」后跑的：去阅读点击成功但后续找书失败？
看失败段（RewardGotoReading 之后）。"""
from pathlib import Path
import re

p = Path(r"G:\project_X\dev\debug\maafw.log")
rows = p.read_text(encoding="utf-8", errors="replace").splitlines()
starts = [i for i, r in enumerate(rows) if "MaaTaskerPostTask" in r and "DirectReadingFlow" in r]
seg = rows[starts[-1]:]
# 找 RewardGotoReading Action.Succeeded 之后的所有节点事件
idx = None
for i, r in enumerate(seg):
    if "RewardGotoReading" in r and "Action.Succeeded" in r:
        idx = i
        break
for r in seg[idx:idx + 14]:
    m = re.search(r"msg=(\S+) \[details=(.{0,110})", r)
    if m:
        print(m.group(1), "|", m.group(2).replace("\\n", " ")[:110])
    elif "WRN" in r or "timeout" in r:
        print(">>", r[:160])
