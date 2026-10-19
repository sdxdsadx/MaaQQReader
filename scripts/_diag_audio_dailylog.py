"""旧 debug/maafw.log 也是 09-09 的旧文件。听书进程活着但哪里在写？
run_maa_ad.py --log-dir G:\project_X\runtime\logs——找 runtime/logs 下
今日新 maafw/debug。gui_DailyAudiobookFlow_*.log 是 0KB（run_task 转发）。
真正输出在 run_maa_ad 的 stdout → daily_all_20260913.log？之前只有 1KB。
再读它（可能刚更新）。"""
from pathlib import Path

log = Path(r"G:\project_X\runtime\logs\daily_all_20260913.log")
print(log.stat().st_size, "bytes")
rows = log.read_text(encoding="utf-8", errors="replace").splitlines()
for r in rows[-25:]:
    print(r[:165])
