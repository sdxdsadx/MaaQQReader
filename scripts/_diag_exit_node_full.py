"""AudiobookExitReaderPage self-loop（next=[自己]）没有出口动作——
definition 里有没有 action？若 recognition 命中但 action=DoNothing
会死循环到 run_task 的轮次上限 → 但那是 timeout 不是 4000。
4000 = MAA 级错误。自看该节点完整定义 + 看 run_maa_ad.py 对 4000 的语义。
先看完整节点。"""
import json
from pathlib import Path

data = json.loads(Path(r"G:\project_X\dev\resource\pipeline\qq_reader_trial.json").read_text(encoding="utf-8"))
print(json.dumps(data["AudiobookExitReaderPage"], ensure_ascii=False, indent=1))
