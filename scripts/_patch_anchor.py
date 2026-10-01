"""全库唯一 [Anchor] 用法=AdReturnStable——异常孤例（其余节点全是普通名）。
MAA 不认这个名字 → 广告链尾断链。修复：改为 LevelAfterCoinAd（广告链
语义上 AdReturnStable 回到奖励页后接「等级福利」页处理，Coin 版更贴）。
同时修 daily_all.py 日志交错问题：每个任务写独立日志文件。"""
import json
from pathlib import Path

pf = Path(r"G:\project_X\dev\resource\pipeline\qq_reader_trial.json")
data = json.loads(pf.read_text(encoding="utf-8"))
data["AdReturnStable"]["next"] = ["LevelAfterCoinAd", "AdDailyComplete", "AdDailyRepeat"]
pf.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
print("AdReturnStable.next →", data["AdReturnStable"]["next"])
