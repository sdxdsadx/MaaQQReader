"""补丁2: 增加 ReadingAlreadyInPage 分支（中断遗留正文页 → 直达计时）。"""
import json
from pathlib import Path

p = Path(r"G:\project_X\dev\resource\pipeline\qq_reader_trial.json")
data = json.loads(p.read_text(encoding="utf-8"))

data["ReadingAlreadyInPage"] = {
    "recognition": "OCR",
    "expected": r"^<第\d+章|^第\d+章|\d+\.\d+%",
    "roi": [0, 0, 720, 1280],
    "action": "DoNothing",
    "post_delay": 500,
    "next": "ReadingWaitOneMinute",
    "focus": "issue #16: 已在正文页（上次中断遗留）——跳过找书直接计时",
}

entry = data["DirectReadingFlow"]
if "ReadingAlreadyInPage" not in (entry.get("next") or []):
    entry["next"] = ["ReadingAlreadyInPage"] + list(entry.get("next") or [])
    print("DirectReadingFlow.next =", entry["next"])

p.write_text(json.dumps(data, ensure_ascii=False, indent=4) + "\n", encoding="utf-8")
print("saved.")
