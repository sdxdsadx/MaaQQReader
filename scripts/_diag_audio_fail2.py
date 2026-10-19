"""听书 36s 就 exit=2——第一棒改的 AudiobookPauseAfterTrial next 链可能
把 json 改出问题（节点不存在/格式错）。看听书段日志尾部。"""
from pathlib import Path

log = Path(r"G:\project_X\runtime\logs\daily_all_20260913.log")
rows = log.read_text(encoding="utf-8", errors="replace").splitlines()
idxs = [i for i, r in enumerate(rows) if "DailyAudiobookFlow start" in r]
seg = rows[idxs[-1]:]
for r in seg[-8:]:
    print(r[:165])
