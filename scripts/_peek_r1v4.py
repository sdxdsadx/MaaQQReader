"""v4 r1 前段分析: 书城页 observe 1..47——runner 现在判 UNKNOWN 后在干什么?
看有没有 step.advance/动作事件（之前 r1-v3 完全无动作行）。"""
from pathlib import Path
import re

p = Path(r"G:\project_X\runtime\logs\supervise_r1.log")
text = p.read_text(encoding="utf-8", errors="replace")
rows = text.splitlines()
print("总行数:", len(rows))

events = [r for r in rows if not r.startswith("[observe")]
print("非 observe 事件行数:", len(events))
for r in events[-12:]:
    print(r[:150])

# OCR 特征计数
for kw in ("看小视频领好礼", "立即观看", "奖品已发放", "安全验证", "安装新版本"):
    cnt = sum(1 for r in rows if kw in r)
    if cnt:
        print(f"{kw}: {cnt}")
