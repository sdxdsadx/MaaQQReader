"""重大进展: 进度 6/12 → 8/12（一次直播广告涨 2 层）！
已完成 8 层。剩余 4 层。当前页已回奖励页。
结论: 广告流程人工预演可通。runner 现在的自动化可以直接跑——
它已修好 GAME_HALL 误判 + HOME 动作能点「再读N分钟领赠币」进奖励页。
但 runner 启动时 app 在奖励页/书架页即可; HOME 动作 tap home_ocr_reward_entry
需要页面有该特征。当前页是奖励页（看小视频领好礼 在 REWARD_HOME 定义）→ 直接跑。

马上重启监督循环（app 停在奖励页，best=8 已在手; supervise 从头计进度无妨，
因为日志里会出现 (8/12) → best=8 → 继续到 12）。"""
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = r"D:\python\python.exe"

print("[final-run] 启动 DailyAdFlow（40min 上限），目标 12/12", flush=True)
log = ROOT / "runtime" / "logs" / "final_run.log"
with open(log, "w", encoding="utf-8") as fh:
    p = subprocess.Popen(
        [PY, "scripts\\run_task.py", "--config", "configs\\qqreader.local.json",
         "--task", "DailyAdFlow", "--timeout-minutes", "40"],
        stdout=fh, stderr=fh, cwd=str(ROOT),
    )

# 看门狗
import re
last_sig, last_change = None, time.time()
while p.poll() is None:
    time.sleep(30)
    if p.poll() is not None:
        break
    try:
        rows = log.read_text(encoding="utf-8", errors="ignore").splitlines()
        sig = rows[-1][:120] if rows else ""
    except OSError:
        sig = ""
    now = time.time()
    if sig != last_sig:
        last_sig, last_change = sig, now
    elif now - last_change > 180:
        print(f"[watchdog] 180s 无变化 → 杀", flush=True)
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(p.pid)], capture_output=True)
        break

text = log.read_text(encoding="utf-8", errors="replace")
for r in text.splitlines():
    if r.startswith(("[outcome]", "[reason]", "[result]")):
        print(r[:140], flush=True)
m = re.findall(r"(\d+)\s*/\s*12", text)
print("本轮最大进度:", max(int(x) for x in m) if m else "无", "/12", flush=True)
