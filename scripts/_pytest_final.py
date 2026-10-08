"""全量测试结果落盘读取（管道截断绕过）。"""
import subprocess

r = subprocess.run(
    ["cmd", "/c", "set PYTHONPATH=G:\\project_X&& D:\\python\\python.exe -m pytest tests/ -q --tb=no"],
    cwd=r"G:\project_X", capture_output=True, text=True, timeout=280, errors="replace")
out = (r.stdout or "") + (r.stderr or "")
tail = [l for l in out.splitlines() if l.strip()][-3:]
print("\n".join(l[:150] for l in tail))
