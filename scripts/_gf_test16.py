"""跑全量测试（排除 RealIntegration 类），保存输出。"""
import subprocess

r = subprocess.run(
    ["cmd", "/c", "dotnet test Gameflow.slnx -c Debug --no-restore --filter Category!=RealIntegration"],
    cwd=r"D:\游戏文件\chatgpt\gameflow", capture_output=True, text=True,
    timeout=280, errors="replace")
out = (r.stdout or "") + (r.stderr or "")
open(r"G:\project_X\runtime\logs\gf_test16.log", "w", encoding="utf-8").write(out)
tail = [l for l in out.splitlines() if l.strip()][-6:]
print("\n".join(l[:160] for l in tail))
