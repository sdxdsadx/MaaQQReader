"""GameFlow ✅ 1294s（21.6min）——Codex 的 GAME_CENTER 修复实机验证通过！
广告 05:15:35 启动中。等广告完成，同时单独跑一轮听书拿干净失败原因
（旧合并日志没抓到它的报错）。不行——设备被广告占用，单跑听书会双开冲突。
改：先读旧合并日志找听书 36s 失败的真实报错行（04:53:15-04:53:51 时段）。"""
from pathlib import Path

log = Path(r"G:\project_X\runtime\logs\daily_all_20260913.log")
rows = log.read_text(encoding="utf-8", errors="replace").splitlines()
start = next(i for i, r in enumerate(rows) if "DailyAudiobookFlow start 04:53:15" in r)
end = next(i for i, r in enumerate(rows) if "DailyGameFlow start" in r and i > start)
for r in rows[start:end]:
    if "observe" not in r:
        print(r[:170])
