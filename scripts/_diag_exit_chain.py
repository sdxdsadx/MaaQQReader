"""04:53 听书失败：status=4000（MAA 内部错误/资源级）。
04:53 的 [Anchor] 断链是我刚才才修的（05:20 左右）——但 4000 是 MAA
资源加载失败。等等——AdReturnStable 在广告链，为什么会让听书 4000？
MAA 加载整个 pipeline 目录 → 任何 json 语法/引用错误都导致资源加载失败
→ 所有 legacy task 4000。但 04:46 阅读成功了（04:53:10 exit=0）……
矛盾！阅读成功说明当时 json 能加载。那 04:53 听书 4000 是别的错——
比如 AudiobookExitReaderPage 新节点定义有问题（OCR expected 格式错）。
看 AudiobookExitReaderPage 及其 next 链上的节点定义。"""
import json
from pathlib import Path

data = json.loads(Path(r"G:\project_X\dev\resource\pipeline\qq_reader_trial.json").read_text(encoding="utf-8"))
cur = "AudiobookExitReaderPage"
depth = 0
while cur and depth < 6:
    v = data.get(cur)
    if v is None:
        print(cur, "MISSING!")
        break
    print(cur, "| post_delay:", v.get("post_delay"),
          "| next:", v.get("next"),
          "| expected:", str(v.get("expected"))[:50],
          "| recognition:", v.get("recognition"))
    nxt = v.get("next") or []
    cur = nxt[0] if nxt else None
    depth += 1
