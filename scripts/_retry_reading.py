"""maafw ERR 是「child return error」——adb 子进程启动失败？
但手动跑同命令成功。可能是 MAA 的 agent 进程环境 PATH 问题。
重试一次 legacy 任务看是否偶发（上次 20:53 失败，success=false status=4000）。"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(r"G:\project_X")
PY = r"D:\python\python.exe"
log = ROOT / "runtime" / "logs" / "reading_flow_retry.log"
runner = ROOT / "_backup_old_project_20260909_200716" / "tools" / "run_maa_ad.py"
cmd = [PY, str(runner), "DirectReadingFlow",
       "--runtime", str(ROOT / "dev"),
       "--resource", str(ROOT / "dev" / "resource"),
       "--device", "127.0.0.1:16384"]
print("[retry] cmd:", " ".join(cmd))
with open(log, "w", encoding="utf-8") as fh:
    p = subprocess.run(cmd, stdout=fh, stderr=subprocess.STDOUT, cwd=str(ROOT), timeout=25 * 60)
raw = log.read_bytes()
for enc in ("utf-8", "gbk"):
    try:
        text = raw.decode(enc)
        break
    except UnicodeDecodeError:
        continue
else:
    text = raw.decode("utf-8", errors="replace")
rows = [r for r in text.splitlines() if r.strip()]
print("总行数:", len(rows))
for r in rows[-6:]:
    print(r[:150])
print("exit:", p.returncode)
