"""列出剩余失败用例明细。"""
import re

log = open(r"G:\project_X\runtime\logs\gf_test16.log", encoding="utf-8", errors="replace").read()
# xUnit 失败块：[FAIL] 后跟错误消息
blocks = re.findall(r"\[FAIL\]\s+([^\r\n]+)", log)
seen = set()
for b in blocks:
    name = b.strip()
    if name not in seen:
        seen.add(name)
        print(name[:150])
