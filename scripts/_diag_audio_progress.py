"""听书任务已跑 25+ 分钟仍无完成行——查 daily_all_*.log 里听书段的实际输出
（maafw 在跑什么节点），判断是挂机中还是卡死。"""
from pathlib import Path
from datetime import datetime

d = datetime.now().strftime("%Y%m%d")
log = Path(rf"G:\project_X\runtime\logs\daily_all_{d}.log")
rows = log.read_text(encoding="utf-8", errors="replace").splitlines()
# 听书段
idx = next((i for i, r in enumerate(rows) if "DailyAudiobookFlow start" in r), None)
if idx is not None:
    seg = rows[idx:]
    print("听书段行数:", len(seg))
    for r in seg[-12:]:
        print(r[:150])
