"""用 UTF-8 严格解码 supervise_r1（*> 重定向实为 UTF-8，前面 GBK 解码错）。
目标：确认 runner 卡在哪个状态、什么广告、什么动作在循环。"""
from pathlib import Path
import re
from collections import Counter

p = Path(r"G:\project_X\runtime\logs\supervise_r1.log")
text = p.read_text(encoding="utf-8", errors="replace")
rows = text.splitlines()
print("总行数:", len(rows))

states = Counter()
for r in rows:
    m = re.search(r"page\.observed\s+(\w+)", r)
    if m:
        states[m.group(1)] += 1
print("状态分布:", states.most_common(10))

adv = [r for r in rows if "step.advance" in r]
print("\n--- 最近 8 条 step.advance ---")
for r in adv[-8:]:
    print(r[:150])

obs_ad = [r for r in rows if "AD_PLAYING" in r or "AD_ENTRY" in r]
print("\nAD_ 相关行数:", len(obs_ad))
if obs_ad:
    print(obs_ad[-1][:150])
