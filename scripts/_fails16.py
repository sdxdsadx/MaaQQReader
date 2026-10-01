"""列出 18 个失败用例名 + 首要错误，一次性分类修复。"""
import re

log = open(r"G:\project_X\runtime\logs\gf_test16.log", encoding="utf-8", errors="replace").read()
fails = re.findall(r"\[FAIL\]\s+(\S+)", log)
from collections import Counter
for name, n in Counter(fails).most_common():
    print(n, name)
print("---")
# 错误类型分布
errs = re.findall(r"(TaskConfigurationValidationException[^\r\n]*|DirectoryNotFoundException[^\r\n]*|FileNotFoundException[^\r\n]*|Assert\.[^\r\n]*)", log)
from collections import Counter as C
for e, n in C(errs).most_common(10):
    print(n, e[:130])
