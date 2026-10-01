"""daily_all 结束：阅读✅ 听书✅ 游戏❌ 广告❌(40min timeout)。
广告也超时了——之前 observe 52-54 显示它也在游戏中心列表页空转（我救场时
拉到游戏中心 tab 而非奖励页，广告任务 HOME→书架→奖励页链没生效？）。
看广告段日志尾部 + 活体当前屏。"""
from pathlib import Path
from datetime import datetime

d = datetime.now().strftime("%Y%m%d")
log = Path(rf"G:\project_X\runtime\logs\daily_all_{d}.log")
rows = log.read_text(encoding="utf-8", errors="replace").splitlines()
idx = next((i for i, r in enumerate(rows) if "DailyAdFlow start" in r), None)
if idx is not None:
    seg = rows[idx:]
    print("广告段行数:", len(seg))
    for r in seg[-6:]:
        print(r[:150])
