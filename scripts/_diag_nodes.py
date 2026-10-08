"""DirectReadingFlow 在 qq_reader_trial.json 里存在。MAA 报 invalid node id…
检查该节点定义是否合法（next 引用的节点是否都存在——MAA 加载时会校验 next，
若 next 指向不存在节点，整条链会被丢）。打印 DirectReadingFlow 及其 next 递归
引用的节点，核对缺失。"""
import json
from pathlib import Path

data = json.loads(Path(r"G:\project_X\dev\resource\pipeline\qq_reader_trial.json").read_text(encoding="utf-8"))
print("DirectReadingFlow:", json.dumps(data["DirectReadingFlow"], ensure_ascii=False)[:400])

missing = set()
def walk(name, seen=None):
    if seen is None:
        seen = set()
    if name in seen or name not in data:
        if name not in data:
            missing.add(name)
        return
    seen.add(name)
    node = data[name]
    for nxt in node.get("next", []):
        walk(nxt, seen)
    for key in ("interrupt", "on_error", "timeout_next"):
        for nxt in node.get(key, []) or []:
            walk(nxt, seen)

walk("DirectReadingFlow")
print("缺失节点:", sorted(missing)[:20])
