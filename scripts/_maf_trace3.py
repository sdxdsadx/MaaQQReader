"""提取 DirectReadingFlow 主链执行序列（非 recognition 子任务）。"""
import re

log = open(r"G:\project_X\runtime\logs\maafw.log", encoding="utf-8", errors="replace").read()

seq = []
for line in log.splitlines():
    if "Actuator::run" in line or "run_next] PipelineTask node done" in line:
        m = re.search(r"\[pipeline_data\.name=([\w]+)\]", line)
        if m:
            seq.append(("ACT", m.group(1)))
    if "task end" in line and '"entry":"DirectReadingFlow"' in line:
        m = re.search(r"\[ret=(\w+)\]", line)
        seq.append(("TASK_END", m.group(1) if m else "?"))

# 只显示主链（ACT 交替 node done 的）
main = []
for kind, name in seq:
    if not main or main[-1] != name:
        main.append(name)
print("主链节点顺序:")
for n in main:
    print("  -", n)
