"""重要发现：app 当前在**奖励页**（今日已获赠币204，今日再读9分钟领20赠币）。
而 legacy DirectReadingFlow 的流程是「StartApp → 书架找书 → 开书读一分钟」，
它假设启动后停在书架，但 app 冷启动实际停在书城/奖励页 → 三个 Terminal 全失败。

且注意：奖励页显示「今日再读9分钟领20赠币」——阅读领币的任务入口其实在
奖励页点「去阅读」或读满 10 分钟。旧流程 DirectReadingFlow 是「开书挂机1分钟」。

真正要跑的逻辑：点书架上的一本书 → 阅读满 1 分钟 → 领取阅读时长赠币。
旧 pipeline 的 ReadingWaitOneMinute 节点链已修好（前几日 work）。

修正方案：给 DirectReadingFlow 补一个「先回书架」的前置节点：
- 新节点 ReadingGotoShelf: OCR「书架」(y≈1250 底部导航) 点击 → next: 三 Terminal
- DirectReadingFlow.next = [ReadingGotoShelf]

改 dev/resource/pipeline/qq_reader_trial.json（新流程权威在 G:\project_I 打包侧
不动）。同时用 pipeline_override? 不——直接改 json 最干净。

实施：json 加节点 + DirectReadingFlow.next 换掉。然后重跑。"""
import json
from pathlib import Path

pf = Path(r"G:\project_X\dev\resource\pipeline\qq_reader_trial.json")
data = json.loads(pf.read_text(encoding="utf-8"))

data["ReadingGotoShelf"] = {
    "action": "Click",
    "target": True,
    "roi": [0, 1200, 180, 80],
    "expected": "书架",
    "post_delay": 2000,
    "next": ["ReadingFindBookTerminal", "ReadingFindBookByTitleTerminal",
             "ReadingOpenFirstShelfBookTerminal"],
    "focus": {
        "ReadingGotoShelf": "点底部「书架」tab 回书架页，再找书（书城页启动时必要）"
    },
}
data["DirectReadingFlow"]["next"] = ["ReadingGotoShelf"]

pf.write_text(json.dumps(data, ensure_ascii=False, indent=4) + "\n", encoding="utf-8")
print("已加 ReadingGotoShelf 节点并重接 DirectReadingFlow.next")
