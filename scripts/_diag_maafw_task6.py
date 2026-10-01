"""又败。看本轮 RewardGotoReading 之后的执行轨迹。"""
from pathlib import Path
import re

p = Path(r"G:\project_X\dev\debug\maafw.log")
rows = p.read_text(encoding="utf-8", errors="replace").splitlines()
starts = [i for i, r in enumerate(rows) if "MaaTaskerPostTask" in r and "DirectReadingFlow" in r]
seg = rows[starts[-1]:]
for r in seg:
    m = re.search(r"msg=(\S+) \[details=(.{0,120})", r)
    if m:
        print(m.group(1), "|", m.group(2).replace("\\n", " ")[:120])
    elif "WRN" in r or "ERR" in r or "timeout" in r:
        print(">>", r[:170])
