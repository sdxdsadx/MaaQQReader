"""mtime 04:28 = Codex 第一棒改的。AudiobookPauseAfterTrial → next=
['AudiobookExitReaderPage']——新节点 AudiobookExitReaderPage 存在吗？
若不存在 → 听书链加载即断 → 36s 失败。这就是根因（大概率）。"""
import json
from pathlib import Path

data = json.loads(Path(r"G:\project_X\dev\resource\pipeline\qq_reader_trial.json").read_text(encoding="utf-8"))
print("AudiobookExitReaderPage 存在:", "AudiobookExitReaderPage" in data)
names = set(data.keys())
bad = [(k, n) for k, v in data.items() for n in (v.get("next") or []) if n not in names]
print("全部断链:", bad)
