"""游戏任务 exit=2（40min timeout，03:27:36）。大概率因为我救场晚了：
02:47-03:04 游戏任务在 AI 朗读页找不到入口空转，03:04 我才拉起游戏中心，
但游戏流程可能需要从奖励页进（入口是「玩游戲领赠币+20赠币→去玩游戏」），
而我把它拉到了游戏中心 tab 而非奖励页 → 仍不匹配 → timeout。
广告任务 03:27:41 已启动（广告任务自己的 HOME→书架→奖励页修复链能自恢复）。
游戏挂机欠 20 分钟，广告跑完后单独重跑游戏。
先看游戏失败日志尾部拿证据，提交 issue 给 Codex。"""
from pathlib import Path
from datetime import datetime

d = datetime.now().strftime("%Y%m%d")
log = Path(rf"G:\project_X\runtime\logs\daily_all_{d}.log")
rows = log.read_text(encoding="utf-8", errors="replace").splitlines()
idx = next((i for i, r in enumerate(rows) if "DailyGameFlow start" in r), None)
if idx is not None:
    seg = rows[idx:]
    print("游戏段行数:", len(seg))
    for r in seg[-8:]:
        print(r[:160])
