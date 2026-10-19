"""AdReturnStable 的 next 首项 [Anchor]LevelAfterAd 指向不存在节点。
近似节点有两个：LevelAfterCoinAd / LevelAfterPointsAd。
查这两个节点的定义判断哪个是正确目标，同时确认这是否 Codex 改的
（git log -p 该文件最近变更）。先看 git blame/历史。"""
import json
import subprocess
from pathlib import Path

r = subprocess.run(["git", "log", "--oneline", "-5", "--", "dev/resource/pipeline/qq_reader_trial.json"],
                   cwd=r"G:\project_X", capture_output=True, text=True, timeout=20)
print(r.stdout)

data = json.loads(Path(r"G:\project_X\dev\resource\pipeline\qq_reader_trial.json").read_text(encoding="utf-8"))
for k in ("LevelAfterCoinAd", "LevelAfterPointsAd", "AdReturnStable"):
    v = data.get(k, {})
    print(k, "| doc:", v.get("doc", "")[:40], "| recog:", v.get("recognition"),
          "| expected:", str(v.get("expected"))[:40])
