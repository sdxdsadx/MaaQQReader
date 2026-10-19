"""Codex 在 504 前已完成 pipeline 重构（277 节点校验通过）但没来得及
写回归测试 + commit。盘点它的遗留：
1. json 已改（AutoReadWatch/RestPopupDismiss 等在）
2. _tmp_issue14_check.py 校验脚本还在（要求删）
3. tests/test_issue14_auto_read.py 未创建
4. 未 commit
先跑全量 pytest 确认现状，再补测试。"""
import subprocess

r = subprocess.run(
    ["cmd", "/c", "set PYTHONPATH=G:\\project_X&& D:\\python\\python.exe -m pytest tests/ -q --tb=no"],
    cwd=r"G:\project_X", capture_output=True, text=True, timeout=280, errors="replace")
out = (r.stdout or "") + (r.stderr or "")
tail = [l for l in out.splitlines() if l.strip()][-4:]
print("\n".join(l[:150] for l in tail))
