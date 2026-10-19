"""codex 是 npm 全局 cmd 脚本（codex.cmd），subprocess 直接调 codex 找不到。
用 shutil.which 定位真实可执行文件再调。"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

codex = shutil.which("codex")
print("codex 路径:", codex)
if not codex:
    sys.exit("未找到 codex")

brief = Path(r"G:\hermes\Hermes Agent CN Desktop\data\hermes-home\cache\anki_task_brief.md").read_text(encoding="utf-8")
prompt = brief + "\n\n工作目录：G:\\hermes\\Hermes Agent CN Desktop\\data\\hermes-home\\cache\n"

env = os.environ.copy()
env["HTTPS_PROXY"] = "http://127.0.0.1:7890"
env["HTTP_PROXY"] = "http://127.0.0.1:7890"

r = subprocess.run(
    [codex, "exec", "--skip-git-repo-check", "--sandbox", "danger-full-access", prompt],
    cwd=r"G:\hermes\Hermes Agent CN Desktop\data\hermes-home\cache",
    capture_output=True, text=True, timeout=550, errors="replace", env=env)
out = (r.stdout or "") + (r.stderr or "")
Path(r"G:\project_X\runtime\logs\codex_anki_task2.log").write_text(out, encoding="utf-8")
print(f"exit={r.returncode}")
print(out[-1200:])
