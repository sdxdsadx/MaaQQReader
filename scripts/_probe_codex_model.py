"""dsh/zcode 帮助里无 astra。codex 本身支持 --model 参数（含自定义网关模型），
用户说的 astra 很可能是 codex 的一个模型档（如 gpt-5.1-codex-astra 之类）
或 GLM 网关模型名。查 codex 可用模型列表。"""
import os
import shutil
import subprocess

codex = shutil.which("codex")
env = os.environ.copy()
env["HTTPS_PROXY"] = "http://127.0.0.1:7890"
r = subprocess.run([codex, "exec", "--help"], capture_output=True, text=True,
                   timeout=30, errors="replace", env=env)
out = (r.stdout or "") + (r.stderr or "")
for line in out.splitlines():
    if "model" in line.lower():
        print(line.strip()[:140])
