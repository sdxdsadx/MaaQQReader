"""missing 字母表 = expected 用了 regex 字符串「第\d+章」被 _diag_nodes 的
walk 当成 next 值遍历？不对——missing 是 expected 的字符被拆开？看：
_A_lreadyInBook 的 expected=r"第\d+章"。walk 只遍历 next/interrupt。字母表
来自哪？「第\d+章」——d 和 \d+ ... 不对，字母 A E R T a d e f g i m n r t x
拼起来像 "WaitOneMinute"+"ReadingExitAfterTimer"+... 啊——
data["ReadingWaitOneMinute"]["post_delay"]=60000 没问题。
问题在 walk()：node.get("next") 某节点的 next 是**字符串**而非列表！
MAA 里 next 必须是列表。哪个节点？"ReadingWaitOneMinute": next 是
"ReadingExitAfterTimer"（字符串！之前 _diag_reading_next 输出显示
next: ReadingExitAfterTimer 没有 []）——walk 对字符串迭代每个字符！
所以 missing=字符串字符集合。这也解释了为何之前链条失败！MAA 5.x 允许
next 为字符串吗？v5 要求 next 必须列表，字符串会导致加载失败——但之前
ReadingWaitOneMinute 没被跑到所以没炸。修：字符串→[字符串]。"""
import json
from pathlib import Path

pf = Path(r"G:\project_X\dev\resource\pipeline\qq_reader_trial.json")
data = json.loads(pf.read_text(encoding="utf-8"))
fixed = []
for name, node in data.items():
    if not isinstance(node, dict):
        continue
    nxt = node.get("next")
    if isinstance(nxt, str):
        node["next"] = [nxt]
        fixed.append(name)
pf.write_text(json.dumps(data, ensure_ascii=False, indent=4) + "\n", encoding="utf-8")
print("修复 next 字符串→列表:", fixed)
