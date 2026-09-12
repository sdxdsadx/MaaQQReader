"""每日任务调度脚本：阅读→听书→游戏→广告，一条命令跑完今日全部任务。
用法: python scripts/daily_all.py [--skip-ad] [--ad-minutes N] [--game-minutes N]
日志: runtime/logs/daily_all_YYYYMMDD.log
任务链:
  1. DailyReadingFlow  (legacy DirectReadingFlow, 挂机阅读攒时长)
  2. DailyAudiobookFlow(legacy, 听书)
  3. DailyGameFlow     (新流程, 在线挂机)
  4. DailyAdFlow       (新流程, 12 层看广告领礼)
任一任务失败不阻断后续（继续跑下一个），最后汇总退出码。
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable
RUN_TASK = ROOT / "scripts" / "run_task.py"
CONFIG = ROOT / "configs" / "qqreader.local.json"
LOGDIR = ROOT / "runtime" / "logs"


def run(task: str, extra: list[str]) -> tuple[bool, float]:
    stamp = datetime.now().strftime("%Y%m%d")
    # 每任务独立日志，避免并发/缓冲交错混串
    log = LOGDIR / f"daily_all_{stamp}_{task}.log"
    cmd = [PY, str(RUN_TASK), "--config", str(CONFIG), "--task", task,
           "--timeout-minutes", "40"] + extra
    t0 = time.time()
    print(f"[{datetime.now():%H:%M:%S}] ▶ {task}", flush=True)
    with open(log, "a", encoding="utf-8") as fh:
        fh.write(f"\n===== {task} start {datetime.now():%H:%M:%S} =====\n")
        proc = subprocess.run(cmd, stdout=fh, stderr=subprocess.STDOUT)
    dt = time.time() - t0
    ok = proc.returncode == 0
    print(f"[{datetime.now():%H:%M:%S}] {'✅' if ok else '❌'} {task} "
          f"({dt:.0f}s) exit={proc.returncode}", flush=True)
    return ok, dt


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-reading", action="store_true")
    ap.add_argument("--skip-audiobook", action="store_true")
    ap.add_argument("--skip-game", action="store_true")
    ap.add_argument("--skip-ad", action="store_true")
    ap.add_argument("--game-minutes", type=int, default=20,
                    help="游戏挂机时长（20 分钟达标领币）")
    args = ap.parse_args()

    plan: list[tuple[str, list[str]]] = []
    if not args.skip_reading:
        plan.append(("DailyReadingFlow", []))
    if not args.skip_audiobook:
        plan.append(("DailyAudiobookFlow", []))
    if not args.skip_game:
        plan.append(("DailyGameFlow",
                     ["--duration-minutes", str(args.game_minutes)]))
    if not args.skip_ad:
        plan.append(("DailyAdFlow", []))

    results: list[tuple[str, bool, float]] = []
    for task, extra in plan:
        ok, dt = run(task, extra)
        results.append((task, ok, dt))
        time.sleep(5)  # 任务间缓冲，避免设备并发

    print("\n===== 汇总 =====")
    for task, ok, dt in results:
        print(f"{'✅' if ok else '❌'} {task} ({dt:.0f}s)")
    return 0 if all(ok for _, ok, _ in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
