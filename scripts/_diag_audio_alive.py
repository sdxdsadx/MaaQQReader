"""maafw.log 是昨天 21:53 关闭的——听书任务用的 legacy run_maa_ad.py
会写自己的 debug 目录。听书 02:15 启动至今 30+ 分钟无完成输出。
检查：①听书子进程还活着吗 ②旧项目 debug 目录最新日志。"""
import subprocess
from pathlib import Path

# ① 子进程树
r = subprocess.run(
    ["wmic", "process", "where", "name='python.exe'", "get", "ProcessId,CommandLine", "/format:list"],
    capture_output=True, text=True, timeout=20)
blocks = [b for b in r.stdout.split("\n\n") if "run_maa_ad" in b or "Audiobook" in b]
print("相关进程块:", len(blocks))
for b in blocks[:3]:
    print(b.strip()[:300])

# ② 旧项目 debug 日志
old_dbg = Path(r"G:\project_X\_backup_old_project_20260909_200716\debug")
if old_dbg.exists():
    for f in sorted(old_dbg.glob("*.log"), key=lambda x: x.stat().st_mtime, reverse=True)[:3]:
        print(f.name, f.stat().st_size // 1024, "KB")
