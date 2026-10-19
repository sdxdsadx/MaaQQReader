"""听书已跑 40+ 分钟（02:15→02:56+），超过 run_task --timeout-minutes 40。
run_task 应该在 40 分钟时杀子进程并返回失败——但 daily_all 的 subprocess.run
还没返回？可能 run_task 的 timeout 机制只对 MAA post 有效，legacy run 的
subprocess 卡住没被杀。看 daily_all_20260913.log 尾部有无 timeout 痕迹 +
run_task.py timeout 实现方式。"""
from pathlib import Path

log = Path(r"G:\project_X\runtime\logs\daily_all_20260913.log")
rows = log.read_text(encoding="utf-8", errors="replace").splitlines()
print("daily log 行数:", len(rows), "尾部:")
for r in rows[-4:]:
    print(r[:150])

src = Path(r"G:\project_X\scripts\run_task.py").read_text(encoding="utf-8")
i = src.find("timeout")
print("\nrun_task timeout 相关:")
while i != -1 and i < len(src):
    line_start = src.rfind("\n", 0, i) + 1
    line_end = src.find("\n", i)
    print(src[line_start:line_end][:150])
    i = src.find("timeout", line_end)
    if i > 20000:
        break
