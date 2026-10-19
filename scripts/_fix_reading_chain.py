"""修 pipeline: 阅读链三个开书节点接上 ReadingWaitOneMinute；听书链验证。"""
import json
from pathlib import Path

p = Path(r"G:\project_X\dev\resource\pipeline\qq_reader_trial.json")
data = json.loads(p.read_text(encoding="utf-8"))

# 阅读链: 三个开书终点全部接「等待 N 分钟 → 退出」
for node in ("ReadingFindBookTerminal", "ReadingFindBookByTitleTerminal",
             "ReadingOpenFirstShelfBookTerminal"):
    if node in data:
        old = data[node].get("next")
        data[node]["next"] = "ReadingWaitOneMinute"
        data[node]["focus"] = data[node].get("focus", "") + "（issue #16: 开书后进入计时等待）"
        print(f"{node}: next {old} -> ReadingWaitOneMinute")

# 阅读等待: post_delay 由 run_task --minutes 动态改（ReadingWaitOneMinute 节点）
w = data.get("ReadingWaitOneMinute", {})
print(f"ReadingWaitOneMinute: post_delay={w.get('post_delay')} next={w.get('next')}")

# 听书链: AudiobookPlaying 命中后应接 AudiobookWaitOneMinute
a = data.get("AudiobookPlaying", {})
print(f"AudiobookPlaying: next={a.get('next')} expected={a.get('expected')}")

p.write_text(json.dumps(data, ensure_ascii=False, indent=4) + "\n", encoding="utf-8")
print("saved.")
