"""本轮失败点：上次成功开书后 app 停在正文页。这次 StartApp 后回奖励页？
还是已在正文页导致「去阅读」找不到？看本轮时间线。"""
from pathlib import Path
import re

p = Path(r"G:\project_X\dev\debug\maafw.log")
rows = p.read_text(encoding="utf-8", errors="replace").splitlines()
starts = [i for i, r in enumerate(rows) if "MaaTaskerPostTask" in r and "DirectReadingFlow" in r]
seg = rows[starts[-1]:]
for r in seg:
    m = re.search(r"msg=(\S+) \[details=(.{0,110})", r)
    if m:
        print(m.group(1), "|", m.group(2).replace("\\n", " ")[:110])
    elif "WRN" in r or "timeout" in r:
        print(">>", r[:160])
