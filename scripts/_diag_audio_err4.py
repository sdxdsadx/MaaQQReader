"""04:53 听书的 legacy 调用行找到：后面紧跟的应该有 success/status JSON。
搜 DailyAudiobookFlow 调用行之后 3 行内的 status 行。"""
from pathlib import Path

log = Path(r"G:\project_X\runtime\logs\daily_all_20260913.log")
rows = log.read_text(encoding="utf-8", errors="replace").splitlines()
for i, r in enumerate(rows):
    if "run_maa_ad.py DailyAudiobookFlow" in r:
        print("== 调用行", i)
        for rr in rows[i:i + 4]:
            print(rr[:200])
        print()
