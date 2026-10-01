"""好消息：广告任务超时但其实干了不少活——当前已在奖励页，
今日已获赠币 150（轮次开始时 140），+10 入账（百度地图任务领取）。
40min 超时是因为 12 层广告+多次 recoveries 用时超出。
看这轮广告日志的 run.finish/steps 判断实际进度，然后：
1) 单独重跑听书（诊断 4000）
2) 广告重跑一轮收尾剩余层数"""
from pathlib import Path

log = Path(r"G:\project_X\runtime\logs\daily_all_20260913_DailyAdFlow.log")
if log.exists():
    rows = log.read_text(encoding="utf-8", errors="replace").splitlines()
    keys = [r for r in rows if any(k in r for k in ("run.finish", "task.success", "[result]", "progress.stall"))]
    for r in keys[-8:]:
        print(r[:160])
    print("总行数:", len(rows))
else:
    print("无独立日志（旧脚本轮）")
