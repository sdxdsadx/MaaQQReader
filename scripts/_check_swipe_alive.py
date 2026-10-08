"""swipe280 日志只有 00:36 一条（taps=15）之后没有新行——可能进程死了？
检查进程与最新日志 mtime。"""
import time
from pathlib import Path

p = Path(r"G:\project_X\runtime\logs\swipe280.log")
print("mtime 距今:", int(time.time() - p.stat().st_mtime), "秒")
print("大小:", p.stat().st_size)
import subprocess
r = subprocess.run(["tasklist"], capture_output=True, text=True, timeout=15)
pl = [l.strip() for l in r.stdout.splitlines() if l.strip().startswith("python")]
print("python 进程:", pl)
