"""进度：再读6分钟→再读3分钟（9 分钟挂机只计了 3 分钟阅读时长？
——挂机时书页可能因无翻页被判定「未在阅读」，或阅读时长按页数计）。
还差 3 分钟。再跑一轮 6 分钟（60000*6=360000ms 覆盖 3 分钟+缓冲）。
WaitOneMinute post_delay 540000→420000 (7min)。"""
import json
from pathlib import Path

pf = Path(r"G:\project_X\dev\resource\pipeline\qq_reader_trial.json")
data = json.loads(pf.read_text(encoding="utf-8"))
data["ReadingWaitOneMinute"]["post_delay"] = 420000
pf.write_text(json.dumps(data, ensure_ascii=False, indent=4) + "\n", encoding="utf-8")
print("post_delay → 420000ms")
