"""MAA 4000 已发生 23 分钟，run_task 仍不退——这是异常挂起（之前同场景
几秒内就退出）。为不阻塞全天任务链，杀掉当前 run_task 让 daily_all 继续
下一任务；同时把挂起问题记 issue 给 Codex（legacy 调用 4000 后 run_task
不退出，疑似 subprocess 等待/恢复逻辑死等）。"""
import subprocess
import time

# 找 run_task pid
r = subprocess.run(
    ["wmic", "process", "where", "name='python.exe'", "get", "ProcessId,CommandLine", "/format:list"],
    capture_output=True, text=True, timeout=20)
for b in r.stdout.split("\n\n"):
    if "run_task.py" in b and "DailyReadingFlow" in b:
        pid = None
        for line in b.splitlines():
            if line.startswith("ProcessId="):
                pid = line.split("=")[1].strip()
        if pid:
            print("杀 run_task pid:", pid)
            subprocess.run(["taskkill", "/PID", pid, "/T", "/F"],
                           capture_output=True, timeout=20)
time.sleep(8)
