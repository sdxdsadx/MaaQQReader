"""奇怪：DailyReadingFlow 12:47 启动，12:47:18 MAA 已报 4000 失败，
但 daily_all 还没打 ❌ 行——legacy run_maa_ad.py 的返回被吞？console3.log
只有一行 ▶。而 app 当前在书城页。可能 legacy 脚本内部在重试？
检查 daily_all 进程是否活着 + run_task 子进程。"""
import subprocess

r = subprocess.run(
    ["wmic", "process", "where", "name='python.exe'", "get", "ProcessId,CommandLine", "/format:list"],
    capture_output=True, text=True, timeout=20)
blocks = [b.strip() for b in r.stdout.split("\n\n") if b.strip()]
for b in blocks:
    if "run_task" in b or "run_maa_ad" in b or "daily_all" in b:
        for line in b.splitlines():
            if line.startswith("CommandLine"):
                print(line[:160])
