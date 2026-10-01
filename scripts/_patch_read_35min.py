"""两个「领取」都点了赠币不涨——说明这两个按钮是「阅读时长兑赠币」档位，
10分钟档对应的是当前进度「再读6分钟」**未达标**（还差6分钟），点击无效
（按钮灰态）。用户指示：**直接按 32 分钟挂机执行**——阅读攒满时长后
20 赠币自动发放，30 分钟档 30 赠币也可领。

执行方案（沿用昨日验证过的 DailyReadingFlow）：
- WaitOneMinute post_delay 已是动态，直接改成 35 分钟挂机（32min+缓冲），
  跑 DailyReadingFlow → 一次攒满。
- 结束后回奖励页验收：再读0分钟 + 赠币 +20（及 30 分钟档若达标 +30）。"""
import json
from pathlib import Path

pf = Path(r"G:\project_X\dev\resource\pipeline\qq_reader_trial.json")
data = json.loads(pf.read_text(encoding="utf-8"))
data["ReadingWaitOneMinute"]["post_delay"] = 2100000  # 35 min
pf.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
print("ReadingWaitOneMinute → 35min 挂机")
