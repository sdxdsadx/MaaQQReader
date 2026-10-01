"""保存完整构建输出到文件，绕过 PS 管道截断。"""
import subprocess

r = subprocess.run(
    ["cmd", "/c", "dotnet build Gameflow.slnx -c Debug --no-restore"],
    cwd=r"D:\游戏文件\chatgpt\gameflow", capture_output=True, text=True,
    timeout=280, errors="replace")
out = (r.stdout or "") + (r.stderr or "")
open(r"G:\project_X\runtime\logs\gf_build.log", "w", encoding="utf-8").write(out)
errs = [l for l in out.splitlines() if "error" in l.lower()]
print(f"exit={r.returncode}, 错误行数={len(errs)}")
for l in errs[:8]:
    print(l[:170])
