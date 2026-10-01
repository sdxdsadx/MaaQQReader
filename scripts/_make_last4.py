"""最后 4 条广告（9/12 → 12/12）：复用同一处理逻辑。"""
import sys
import time
from pathlib import Path

code = Path(r"G:\project_X\scripts\_ad_batch_11.py").read_text(encoding="utf-8")
code = code.replace("TARGET = 12", "TARGET = 12")
code = code.replace("for ad_no in range(2, 13):", "for ad_no in range(9, 17):")
code = code.replace('print(f"===== 第 {ad_no} 条', 'print(f"===== 补跑 第 {ad_no} 条')
Path(r"G:\project_X\scripts\_ad_batch_last4.py").write_text(code, encoding="utf-8")
print("last4 脚本已生成")
