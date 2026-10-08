"""maafw.log 是活体（13MB，持续更新）——听书在跑。看它最新节点动作确认
正常挂机还是卡死。"""
from pathlib import Path

p = Path(r"G:\project_X\dev\debug\maafw.log")
rows = p.read_text(encoding="utf-8", errors="replace").splitlines()
tail = rows[-40:]
for r in tail:
    if any(k in r for k in ("NextList", "RunTask", "node", "completed", "Succ", "Fail", "Timeout")):
        print(r[:160])
