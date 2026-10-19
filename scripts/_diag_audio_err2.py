"""GameFlow 完整证据链拿到了：SUCCESS，123 steps，recoveries=14，
20min 挂机（WAIT x10s）+ 领奖 + 退出回 REWARD_HOME，记录已存。
但听书 36s 失败的真实 stderr 还没找到——它在 04:53:51 行附近。
直接搜那个时段的 ERR/status。"""
from pathlib import Path

log = Path(r"G:\project_X\runtime\logs\daily_all_20260913.log")
rows = log.read_text(encoding="utf-8", errors="replace").splitlines()
start = next(i for i, r in enumerate(rows) if "DailyAudiobookFlow start 04:53:15" in r)
seg = rows[start:start + 4]
print("\n".join(r[:200] for r in seg))
# 也搜 04:53 时段的 legacy/maafw 行
for r in rows:
    if ("04:53:1" in r or "04:53:2" in r or "04:53:3" in r or "04:53:4" in r or "04:53:5" in r) and ("legacy" in r or "ERR" in r or "success" in r or "status" in r or "failed" in r):
        print(r[:200])
