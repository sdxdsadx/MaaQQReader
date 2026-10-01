"""dev 侧找书三节点 next=None——断链没接计时！接上：
三节点 next=[ReadingWaitOneMinute]（该节点 post_delay=2100000ms=35min?
——那是 legacy 等待参数被 run_task --minutes 改写的钩子。保持不动，仅接链。）"""
import json
from pathlib import Path

pf = Path(r"G:\project_X\dev\resource\pipeline\qq_reader_trial.json")
data = json.loads(pf.read_text(encoding="utf-8"))
for n in ("ReadingFindBookTerminal", "ReadingFindBookByTitleTerminal",
          "ReadingOpenFirstShelfBookTerminal"):
    data[n]["next"] = ["ReadingWaitOneMinute"]
pf.write_text(json.dumps(data, ensure_ascii=False, indent=4) + "\n", encoding="utf-8")
print("已接：找书节点 → ReadingWaitOneMinute → ReadingExitAfterTimer")
