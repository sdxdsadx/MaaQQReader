"""ReadingGotoShelf 起跑且 Click 成功。看它后面（找书三节点 + 失败点）。"""
from pathlib import Path
import re

p = Path(r"G:\project_X\dev\debug\maafw.log")
rows = p.read_text(encoding="utf-8", errors="replace").splitlines()
starts = [i for i, r in enumerate(rows) if "MaaTaskerPostTask" in r and "DirectReadingFlow" in r]
seg = rows[starts[-1]:]
for r in seg:
    m = re.search(r"msg=(\S+) \[details=(.{0,130})", r)
    if m:
        print(m.group(1), "|", m.group(2).replace("\\n", " ")[:130])
    elif "WRN" in r or "ERR" in r:
        print(r[:170])
