"""提取 maafw.log 中 DirectReadingFlow 链条的 reco hit 细节与 task end。"""
import re

log = open(r"G:\project_X\runtime\logs\maafw.log", encoding="utf-8", errors="replace").read()

# 1. 所有 reco hit 行（带节点名）
for line in log.splitlines():
    if "reco hit" in line and "PipelineTask" in line:
        m = re.search(r"reco hit \[result=.*?\]", line)
        if m:
            print("HIT:", line[line.find("reco hit"):][:200])

# 2. task end cb_detail
for line in log.splitlines():
    if "task end" in line:
        i = line.find("cb_detail")
        print("END:", line[i:][:400])

# 3. PipelineTask node done 前后的节点名
names = re.findall(r"\[pipeline_data\.name=(\w+)\]", log)
print("\n执行过的 pipeline 节点序列:")
seen = []
for n in names:
    if not seen or seen[-1] != n:
        seen.append(n)
print("  " + " → ".join(dict.fromkeys(seen)))
