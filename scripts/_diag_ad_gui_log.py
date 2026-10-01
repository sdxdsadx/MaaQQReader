"""广告段在 daily_all log 只有 1 行——run_task 的 observe 输出去哪了？
看 gui_DailyAdFlow_*.log（run_task 转发文件）和最新 observe 记录。"""
from pathlib import Path

d = Path(r"G:\project_X\runtime\logs")
files = sorted(d.glob("gui_DailyAdFlow*.log"), key=lambda p: p.stat().st_mtime, reverse=True)
for f in files[:2]:
    print("==", f.name, f.stat().st_size // 1024, "KB")
    rows = f.read_text(encoding="utf-8", errors="replace").splitlines()
    for r in rows[-8:]:
        print(r[:150])
