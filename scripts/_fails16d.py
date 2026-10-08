"""统计当前失败数 + 各失败的首条错误。"""
import re

log = open(r"G:\project_X\runtime\logs\gf_test16.log", encoding="utf-8", errors="replace").read()
m = re.findall(r"失败!  - 失败:\s*(\d+)，通过:\s*(\d+)", log)
print("结果:", m)
msgs = re.findall(r"错误消息:\s*\r?\n\s*([^\r\n]+)", log)
seen = set()
for msg in msgs:
    if msg[:70] not in seen:
        seen.add(msg[:70])
        print("*", msg[:150])
