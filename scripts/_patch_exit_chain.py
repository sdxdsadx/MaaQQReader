"""status 4000 = MaaTaskerWait 返回的 task 结束状态=4000（internal error /
任务节点执行失败）。MAA v5: 2000=invalid,3000=succeeded,4000=failed。
即 pipeline 任务链执行失败退出——听书链跑到某节点 fail。
AudiobookExitReaderPage 的 self-loop max_hit=4：命中 4 次后 next 耗尽 →
任务失败(4000)！因为 post-pause 页面 OCR 匹配「AI朗读|会员本书免费听|...」
一直命中（当前页确实是朗读页）→ BACK 4 次 → max_hit 耗尽 → 4000。
若 BACK 后仍停在朗读相关页（比如简介页/书城），继续命中 expected → 失败。
修复：max_hit=4 太小 + self-loop 需要出口到兜底（比如 AudiobookBackUntilShelf
或直接 null 让任务结束）。其实任务收尾本意是「退到主页即可结束」，
改成命中后 next=[]（自然完成）+ max_hit=6。MAA 语义：next 为空列表则任务
完成？MAA v5 next=None/空=链结束=成功。改成 next=[]。"""
import json
from pathlib import Path

pf = Path(r"G:\project_X\dev\resource\pipeline\qq_reader_trial.json")
data = json.loads(pf.read_text(encoding="utf-8"))
n = data["AudiobookExitReaderPage"]
n["max_hit"] = 6
n["next"] = []
pf.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
print("AudiobookExitReaderPage: max_hit=6, next=[] (链自然结束=成功)")
