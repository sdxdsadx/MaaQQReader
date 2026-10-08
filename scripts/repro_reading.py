"""复现用户的 DailyReadingFlow 失败: 1 分钟等待的任务跑 60 秒。"""
import subprocess
import sys
import time

cmd = [
    sys.executable,
    r"G:\project_X\scripts\run_task.py",
    "--config", r"G:\project_X\configs\qqreader.local.json",
    "--task", "DailyReadingFlow",
    "--minutes", "1",
    "--timeout-minutes", "6",
]
print("[repro] launching:", " ".join(cmd), flush=True)
t0 = time.time()
p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
for line in p.stdout:
    print(line.rstrip()[:160], flush=True)
rc = p.wait()
print(f"[repro] exit={rc} elapsed={time.time()-t0:.1f}s", flush=True)
