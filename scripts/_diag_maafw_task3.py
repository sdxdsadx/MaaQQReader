"""继续: 拿 invalid node id 前后各 15 行原始日志（不过滤），确认炸点。"""
from pathlib import Path

p = Path(r"G:\project_X\dev\debug\maafw.log")
rows = p.read_text(encoding="utf-8", errors="replace").splitlines()
for i, r in enumerate(rows):
    if "invalid node id" in r:
        for x in rows[max(0, i - 14):i + 6]:
            print(x[:230])
        break
