"""时间线只到 controller。要找 DirectReadingFlow 任务执行段——搜 post_task 之后
所有含 task/next/complete 的行。"""
from pathlib import Path

p = Path(r"G:\project_X\dev\debug\maafw.log")
rows = p.read_text(encoding="utf-8", errors="replace").splitlines()
start = None
for i, r in enumerate(rows):
    if "MaaTaskerPostTask" in r and "DirectReadingFlow" in r:
        start = i
        break
if start is None:
    print("没找到 post_task")
else:
    for r in rows[start:start + 40]:
        if any(k in r for k in ("INF", "WRN", "ERR", "DBG")):
            # 只打关键行
            if any(k in r for k in ("PostTask", "next", "complete", "invalid", "run", "node", "focus", "TaskNS")):
                print(r[:200])
