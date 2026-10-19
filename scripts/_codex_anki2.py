"""Codex 没读到简报（它回复"请把源材料发来"）——prompt 传参没问题但它
可能忽略了。改用最直接的方式：把任务写成 prompt 文件后用 codex 的
`-` stdin 模式？codex exec 不支持。最稳：prompt 第一行就给绝对路径指令，
并用 verbatim 明确指令。先快速验证 codex 是否能读到文件：跑一个最小任务
"读取 X 文件第一行并输出"。"""
import os
import shutil
import subprocess
from pathlib import Path

codex = shutil.which("codex")
prompt = (
    "读取文件 G:\\hermes\\Hermes Agent CN Desktop\\data\\hermes-home\\cache\\anki_task_brief.md，"
    "严格按其中任务执行。该简报包含源材料路径、格式要求、产出路径和报告要求。"
    "不要询问，直接执行并在最终输出报告。"
)
env = os.environ.copy()
env["HTTPS_PROXY"] = "http://127.0.0.1:7890"
env["HTTP_PROXY"] = "http://127.0.0.1:7890"
r = subprocess.run(
    [codex, "exec", "--skip-git-repo-check", "--sandbox", "danger-full-access", prompt],
    cwd=r"G:\hermes\Hermes Agent CN Desktop\data\hermes-home\cache",
    capture_output=True, text=True, timeout=550, errors="replace", env=env)
out = (r.stdout or "") + (r.stderr or "")
Path(r"G:\project_X\runtime\logs\codex_anki_task3.log").write_text(out, encoding="utf-8")
print(f"exit={r.returncode}")
print(out[-1500:])
