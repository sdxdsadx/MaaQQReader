"""根因: maafw「invalid node id, handle error [node.name=DirectReadingFlow]」——
DirectReadingFlow 节点不在加载的 resource bundle 里（pipeline json 里没有该节点名）。
看 dev/resource/pipeline/*.json 里的节点名列表，确认阅读流程节点的真实名字。"""
import json
from pathlib import Path

rp = Path(r"G:\project_X\dev\resource\pipeline")
for f in sorted(rp.glob("*.json")):
    try:
        data = json.loads(f.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"{f.name}: 解析失败 {e}")
        continue
    names = list(data.keys())
    hit = [n for n in names if "ead" in n or "阅读" in n or "Direct" in n]
    print(f"{f.name}: {len(names)} 节点; 阅读相关: {hit[:8]}")
