"""又失败——看这次 maafw 时间线：ReadingGotoShelf 有没有起跑、卡在哪。"""
from pathlib import Path

p = Path(r"G:\project_X\dev\debug\maafw.log")
rows = p.read_text(encoding="utf-8", errors="replace").splitlines()
# 找最后一次 DirectReadingFlow post_task 段
starts = [i for i, r in enumerate(rows) if "MaaTaskerPostTask" in r and "DirectReadingFlow" in r]
if not starts:
    print("no task")
else:
    seg = rows[starts[-1]:]
    for r in seg:
        if any(k in r for k in ("Starting", "Succeeded", "Failed", "invalid", "WRN", "timeout", "reco [result")):
            # 截取 msg 与 name/roc 关键字段
            import re
            m = re.search(r"msg=(\S+) \[details=(.{0,160})", r)
            if m:
                print(m.group(1), "|", m.group(2).replace("\\n", " ")[:150])
            else:
                print(r[:170])
