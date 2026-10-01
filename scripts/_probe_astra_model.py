"""codex 当前默认模型 gpt-5.6-sol。astra 大概率是 codex 的另一模型档。
试 `-m astra` 直接跑一个最小探测（若网关支持会返回，不支持报错）。
直接试 'gpt-5.6-astra' 与 'astra' 两个常见命名。"""
import os
import shutil
import subprocess

codex = shutil.which("codex")
env = os.environ.copy()
env["HTTPS_PROXY"] = "http://127.0.0.1:7890"
for model in ("astra", "gpt-5.6-astra"):
    r = subprocess.run(
        [codex, "exec", "--skip-git-repo-check", "-m", model,
         "回复一个词：pong"],
        cwd=r"G:\project_X", capture_output=True, text=True, timeout=90,
        errors="replace", env=env)
    out = (r.stdout or "") + (r.stderr or "")
    ok = "pong" in out.lower()
    print(f"model={model}: exit={r.returncode} pong={ok}")
    if not ok:
        print("  err:", out[-200:].replace(chr(10), " | "))
    if ok:
        break
