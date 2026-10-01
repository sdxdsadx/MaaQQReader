"""修听书链: AudiobookPlaying 预期加「正在播放第N章」；开书节点接等待链。"""
import json
from pathlib import Path

p = Path(r"G:\project_X\dev\resource\pipeline\qq_reader_trial.json")
data = json.loads(p.read_text(encoding="utf-8"))

# 1) AudiobookPlaying: 当前 UI 实测文案「正在播放第315章烈拳九宫！」
ap = data.get("AudiobookPlaying", {})
old = ap.get("expected")
ap["expected"] = "AI朗读|会员本书免费听|正在播放第"
print(f"AudiobookPlaying.expected: {old} -> {ap['expected']}")

# 2) AudiobookFindBook 预期加实测在架书目（柯学验尸官=当前播放书在书架可见）
ab = data.get("AudiobookFindBook", {})
old2 = ab.get("expected")
ab["expected"] = "全职法师|柯学验尸官|正在播放第"
print(f"AudiobookFindBook.expected: {old2} -> {ab['expected']}")

# 3) AudiobookOpenFirstShelfBook 的 ^书架.*$ roi 检查（顶部 tab）
aof = data.get("AudiobookOpenFirstShelfBook", {})
print(f"AudiobookOpenFirstShelfBook: expected={aof.get('expected')} roi={aof.get('roi')} next={aof.get('next')}")

# 4) 中断遗留播放页直达分支（同阅读链思路）
if "AudiobookAlreadyPlaying" not in data:
    data["AudiobookAlreadyPlaying"] = {
        "recognition": "OCR",
        "expected": r"正在播放第\d+章|AI朗读",
        "roi": [0, 300, 720, 980],
        "action": "DoNothing",
        "post_delay": 500,
        "next": "AudiobookWaitOneMinute",
        "focus": "issue #16: 已在播放页（中断遗留）——直接进入计时",
    }
    entry = data["DailyAudiobookFlow"]
    if "AudiobookAlreadyPlaying" not in (entry.get("next") or []):
        entry["next"] = ["AudiobookAlreadyPlaying"] + list(entry.get("next") or [])
        print("DailyAudiobookFlow.next =", entry["next"])

# 5) AudiobookWaitOneMinute 计时节点确认
aw = data.get("AudiobookWaitOneMinute", {})
print(f"AudiobookWaitOneMinute: post_delay={aw.get('post_delay')} next={aw.get('next')}")

p.write_text(json.dumps(data, ensure_ascii=False, indent=4) + "\n", encoding="utf-8")
print("saved.")
