"""gui 日志只有 task start 一行——run_task 的 stderr（python traceback?）
没落盘。36s exit=2 的真实输出被 daily_all.py 的 subprocess 丢了？
不——daily_all.py 用 stdout=fh stderr=STDOUT 都写进 daily log。
但 04:53 时段除了 GameFlow 的输出啥都没有！说明 Audiobook run_task
的输出真的没写进来……啊，明白了：**04:53 那轮 daily_all 是旧脚本
（合并日志），Audiobook 的 run_task 输出 '...start 04:53:15' 之后
立刻被 GameFlow 的 40min 输出淹没——不对，GameFlow 05:15 才结束，
Audiobook 04:53:51 就 exit=2 了，时间上 Audiobook 输出在前。
再精确点：直接找 exit=2 的相关行以及 04:53:5x 的行。"""
from pathlib import Path

log = Path(r"G:\project_X\runtime\logs\daily_all_20260913.log")
rows = log.read_text(encoding="utf-8", errors="replace").splitlines()
for i, r in enumerate(rows):
    if "DailyAudiobookFlow" in r and "start" in r:
        for rr in rows[i:i + 3]:
            print("A:", rr[:150])
        break
# 搜关键失败词
for r in rows:
    if any(w in r for w in ("[legacy]", "[ERR]", "status\": 4", "status\": 2", "failed", "Fatal", "Traceback")):
        if "04:53" in r or "04:5" in r or "legacy" in r or "Traceback" in r:
            print("F:", r[:180])
