"""检查听书挂机目标时长：旧流程 DailyAudiobookFlow 的 pipeline 里等待节点
post_delay 是多少。若挂机 30 分钟属正常（听书攒时长），等就是。
先 grep legacy resource pipeline。"""
import json
from pathlib import Path

for p in Path(r"G:\project_X\dev\resource\pipeline").glob("*.json"):
    data = json.loads(p.read_text(encoding="utf-8"))
    hits = {k: v for k, v in data.items() if "Audio" in k or "听书" in str(v.get("doc", ""))}
    if hits:
        print("==", p.name)
        for k, v in hits.items():
            print(f"  {k}: post_delay={v.get('post_delay')} next={v.get('next')}")
