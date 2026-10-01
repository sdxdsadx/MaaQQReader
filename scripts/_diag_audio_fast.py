"""听书 59s exit=2 快速失败——昨天同样的 4000 挂起模式变体。
看日志尾部确认错误类型，然后提交 issue 派 Codex（把今天两大问题合一个 issue：
①legacy 4000 后 run_task 挂死不退 ②听书 59s 快速失败）。
游戏在跑，等它。"""
from pathlib import Path
from datetime import datetime

d = datetime.now().strftime("%Y%m%d")
log = Path(rf"G:\project_X\runtime\logs\daily_all_{d}_DailyAudiobookFlow.log")
rows = log.read_text(encoding="utf-8", errors="replace").splitlines()
for r in rows[-6:]:
    print(r[:170])
