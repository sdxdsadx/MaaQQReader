"""daily_all 跳过阅读轮结束：听书✅ 游戏✅ 广告❌40min超时。
广告超时分析（结合实时观察）：app 全程停在奖励页游戏卡附近
（玩游戏领赠币+20/再玩1分钟），广告任务没在看广告——
被「玩游戏领赠币」卡片吸引？还是入口识别走了偏？
看这轮广告日志的关键 observe，判断它在干什么。"""
from pathlib import Path
from datetime import datetime

d = datetime.now().strftime("%Y%m%d")
log = Path(rf"G:\project_X\runtime\logs\daily_all_{d}_DailyAdFlow.log")
rows = log.read_text(encoding="utf-8", errors="replace").splitlines()
print("行数:", len(rows))
for r in rows[-10:]:
    print(r[:150])
