"""DirectReadingFlow 起跑正常（StartApp DirectHit 成功）。invalid node id 在后面。
抓从「Action」开始到 invalid 之间的全部行，看是哪个节点句柄炸了。"""
from pathlib import Path

p = Path(r"G:\project_X\dev\debug\maafw.log")
rows = p.read_text(encoding="utf-8", errors="replace").splitlines()
# 找到第一个 Action.Starting（DirectReadingFlow 的）之后的 40 行原样输出
idx = None
for i, r in enumerate(rows):
    if "Node.Action.Starting" in r and "DirectReadingFlow" in r:
        idx = i
        break
if idx is None:
    # 退化: 找 invalid 前的 30 行
    for i, r in enumerate(rows):
        if "invalid node id" in r:
            idx = i - 30
            break
for r in rows[idx:idx + 40]:
    if any(k in r for k in ("Starting", "Succeeded", "Failed", "invalid", "WRN", "ERR", "run_out", "NextList")):
        print(r[:210])
