"""AnkiConnect 已可达(version=6)。导入 18 张卡到牌组 高数::考研复习。
先建牌组，再逐卡 canAddNotes + addNotes，最后统计。"""
import json
import csv
import time
import urllib.request
from pathlib import Path

FINAL = Path(r"G:\hermes\Hermes Agent CN Desktop\data\hermes-home\cache\documents\高数卡片_anki导入_final.txt")
DECK = "高数::考研复习"


def anki(action, **params):
    body = json.dumps({"action": action, "version": 6, "params": params}).encode("utf-8")
    req = urllib.request.Request("http://127.0.0.1:8765", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    if data.get("error"):
        raise RuntimeError(f"{action}: {data['error']}")
    return data["result"]


# 建牌组（已存在则忽略）
try:
    anki("createDeck", deck=DECK)
    print(f"牌组已就绪: {DECK}")
except RuntimeError as e:
    print(f"建牌组: {e}")

with open(FINAL, encoding="utf-8-sig", newline="") as fh:
    rows = [r for r in csv.reader(fh, delimiter="\t", quotechar='"') if any(r)]
print(f"读取卡片: {len(rows)} 条")

notes = []
for front, back, tags in rows:
    notes.append({
        "deckName": DECK,
        "modelName": "Basic",
        "fields": {"Front": front, "Back": back},
        "tags": tags.split(),
        "options": {"allowDuplicate": False},
    })

# 检查可添加性
checks = anki("canAddNotesWithErrorDetail", notes=notes)
addable = [n for n, c in zip(notes, checks) if c.get("canAdd")]
skipped = len(notes) - len(addable)
print(f"可添加 {len(addable)}，跳过(重复等) {skipped}")

if addable:
    result = anki("addNotes", notes=addable)
    added = sum(1 for n in result if isinstance(n, (int, str)) and n)
    print(f"成功导入 {added} 张")

# 验证
count = anki("deckStats", deck=DECK) if False else anki("findCards", query=f'deck:"{DECK}"')
print(f"牌组内卡片总数: {len(count)}")
