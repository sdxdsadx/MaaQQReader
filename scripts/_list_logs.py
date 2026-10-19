"""daily_all_YYYYMMDD.log 竟无听书段？直接列 runtime/logs 最新文件看听书
输出到哪了。"""
from pathlib import Path

d = Path(r"G:\project_X\runtime\logs")
files = sorted(d.glob("*.log"), key=lambda p: p.stat().st_mtime, reverse=True)[:6]
for f in files:
    print(f"{f.name}  {f.stat().st_size//1024}KB  mtime={f.stat().st_mtime}")
