"""节点 DirectReadingFlow 存在于 qq_reader_trial.json 里，但 MAA 报 invalid node id。
检查: resource bundle 加载的是 dev/resource 吗？qq_reader_trial.json 在 dev/resource/pipeline？
另外对比: DailyAdFlow 之前能跑吗？run_maa_ad.py 用 --resource 默认 G:\project_X\dev\resource。
再查节点 DirectReadingFlow 的定义是否有 next/结构问题（MAA 对节点名一样认，除非 json 没被加载）。
看 dev/resource 下有几个 pipeline json。"""
import json
from pathlib import Path

dev = Path(r"G:\project_X\dev\resource")
print("pipeline 目录:", list((dev / "pipeline").glob("*.json")))
print("interface.json:", (dev / "interface.json").exists())
ij = dev / "interface.json"
if ij.exists():
    data = json.loads(ij.read_text(encoding="utf-8"))
    task_names = [t.get("name") for t in data.get("task", [])]
    print("interface task entries:", task_names[:12])
    # DirectReadingFlow 的 pipeline 定义位置
    for t in data.get("task", []):
        if "Read" in str(t.get("name", "")):
            print(json.dumps(t, ensure_ascii=False)[:300])
