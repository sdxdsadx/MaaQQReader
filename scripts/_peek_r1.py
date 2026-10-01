"""找 r1 里的 step/action 事件行（格式可能是 [NNNNNN.NNN] step.advance ...）。"""
from pathlib import Path
import re
from collections import Counter

p = Path(r"G:\project_X\runtime\logs\supervise_r1.log")
text = p.read_text(encoding="utf-8", errors="replace")
rows = text.splitlines()
print("总行数:", len(rows))

# 非 observe 行 = 事件行
events = [r for r in rows if not r.startswith("[observe")]
print("非 observe 行数:", len(events))
for r in events[-15:]:
    print(r[:160])
