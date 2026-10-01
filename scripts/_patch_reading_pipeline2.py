"""关键领悟：app 停在**奖励页**（不是书城）。「点书架→开书」流程的前提不成立。
奖励页底部可能没有「书架」tab（此页是弹窗式/嵌套页）。

但注意——**阅读领币的正确入口就在本页**：
- 「去阅读」(x=561, y=420)：跳回书架/阅读页，读满 1 分钟回来自动领
- 「今日再读9分钟领20赠币」：读满 1 分钟即可 +20

方案修订：改 DirectReadingFlow 链——
DirectReadingFlow(StartApp) → ReadingGotoShelfOrReward：
- 新节点 RewardGotoReading: OCR「去阅读」点击 → next: 三找书节点
- ReadingGotoShelf: OCR「书架」→ next: 三找书节点
两个入口节点并列在 DirectReadingFlow.next，MAA 轮询识别谁在屏点谁。

实施：json 加 RewardGotoReading；DirectReadingFlow.next=[RewardGotoReading, ReadingGotoShelf]。"""
import json
from pathlib import Path

pf = Path(r"G:\project_X\dev\resource\pipeline\qq_reader_trial.json")
data = json.loads(pf.read_text(encoding="utf-8"))

data["RewardGotoReading"] = {
    "action": "Click",
    "target": True,
    "expected": "去阅读",
    "post_delay": 2500,
    "next": ["ReadingFindBookTerminal", "ReadingFindBookByTitleTerminal",
             "ReadingOpenFirstShelfBookTerminal"],
    "focus": {"RewardGotoReading": "奖励页点「去阅读」跳回阅读侧，再找书"},
}
data["DirectReadingFlow"]["next"] = ["RewardGotoReading", "ReadingGotoShelf"]

pf.write_text(json.dumps(data, ensure_ascii=False, indent=4) + "\n", encoding="utf-8")
print("已加 RewardGotoReading，DirectReadingFlow.next=[RewardGotoReading, ReadingGotoShelf]")
