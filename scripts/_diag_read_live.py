"""阅读任务 15 分钟还在跑——查活体：是 35min 挂机（上轮改的
ReadingWaitOneMinute post_delay=2100000）还是卡死。看任务日志段+活体页面。"""
from pathlib import Path
from datetime import datetime

d = datetime.now().strftime("%Y%m%d")
log = Path(rf"G:\project_X\runtime\logs\daily_all_{d}_DailyReadingFlow.log")
if log.exists():
    rows = log.read_text(encoding="utf-8", errors="replace").splitlines()
    print("日志行数:", len(rows))
    for r in rows[-6:]:
        print(r[:150])
else:
    print("无独立日志")
