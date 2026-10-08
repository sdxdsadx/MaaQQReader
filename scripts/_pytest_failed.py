"""找 2 个失败用例。cmd 方式避免 & 解析问题。"""
import subprocess

r = subprocess.run(
    ["cmd", "/c", "set PYTHONPATH=G:\\project_X&& D:\\python\\python.exe -m pytest tests/ -q --tb=no"],
    cwd=r"G:\project_X", capture_output=True, text=True, timeout=280)
tail = (r.stdout or "") + (r.stderr or "")
for line in tail.splitlines():
    if "FAILED" in line or "failed" in line or "passed" in line:
        print(line[:160])
