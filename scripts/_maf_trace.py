"""提取 maafw.log 中 DirectReadingFlow 链条的关键 reco/next 决策。"""
import re

log = open(r"G:\project_X\runtime\logs\maafw.log", encoding="utf-8", errors="replace").read()
# 找 reco hit 与 run_next 决策
for m in re.finditer(r"reco hit \[result=\{[^}]*\}[^\]]*\][^\n]*", log):
    print("HIT:", m.group(0)[:150])
for m in re.finditer(r"\[cur_node_=([\w]+)[^\]]*\] ([^\n]{0,120})", log):
    print("NODE:", m.group(1), "|", m.group(2)[:110])
for m in re.finditer(r"task end: \[cb_detail=(\{[^\n]{0,300})", log):
    print("END:", m.group(1)[:260])
