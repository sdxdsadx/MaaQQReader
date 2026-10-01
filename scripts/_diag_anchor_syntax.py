"""AudiobookExitReaderPage 存在，听书链完好。唯一断链 [Anchor]LevelAfterAd
在广告链 AdReturnStable。[Anchor] 前缀在 MAA 中是合法 anchor 语法吗？
MAA v5 官方支持 <AnchorName> 形式？查 dev 下旧版 json 是否同款语法
（02:15 听书成功时该断链应已存在——因为 AdReturnStable 是广告链节点，
02:15 广告任务没跑，无法证伪）。看其他 pipeline json 有无 [Anchor]。"""
import json
from pathlib import Path

for p in Path(r"G:\project_X\dev\resource\pipeline").glob("*.json"):
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        continue
    hits = [(k, n) for k, v in data.items() for n in (v.get("next") or []) if str(n).startswith("[")]
    if hits:
        print(p.name, hits[:6])
print("done")
