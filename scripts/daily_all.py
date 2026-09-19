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

if str(Path(__file__).resolve().parents[1]) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from qqreader.workflow import (
    DailyFlowRecorder,
    DailyFlowRun,
    FlowRunState,
    FlowStepSnapshot,
)

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable
RUN_TASK = ROOT / "scripts" / "run_task.py"
CONFIG = ROOT / "configs" / "qqreader.local.json"
LOGDIR = ROOT / "runtime" / "logs"


def _find_nearby_claim(boxes, card_markers=("每日听书", "已听")):
    """返回与目标任务卡同一行的领取按钮 OCR 框；已在奖励页也可调用。"""
    cards = [item for item in boxes if any(marker in item[0] for marker in card_markers)]
    claims = [item for item in boxes if item[0].strip() in {"领取", "立即领取"}]
    for _card_text, card_box in cards:
        nearby = [item for item in claims if abs(item[1][1] - card_box[1]) < 150]
        if nearby:
            return nearby[0]
    return None


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


def claim_audiobook_reward() -> bool:
    """听书 SUCCESS 后去奖励页领「每日听书30分钟+20赠币」。
    路径：书架 → 时长兑赠币入口 → 下滑找听书卡「立即领取」→ 点。"""
    import subprocess
    import sys as _sys
    _ROOT2 = Path(__file__).resolve().parents[1]
    if str(_ROOT2) not in _sys.path:
        _sys.path.insert(0, str(_ROOT2))
    from qqreader.config import load_config
    from qqreader.maa.factory import build_maa_client

    config = load_config("configs/qqreader.local.json")
    client = build_maa_client(config)
    try:
        client.connect()
    except Exception as exc:
        print(f"[听书领取] 连接失败: {exc}", flush=True)
        return False

    def ocr():
        s = client.screencap()
        return client.recognize("OCR", {}, s).text_boxes()

    def try_claim_on_current_page() -> bool:
        claim = _find_nearby_claim(ocr())
        if claim is None:
            return False
        _text, box = claim
        client.swipe(
            box[0] + box[2] // 2,
            box[1] + box[3] // 2,
            box[0] + box[2] // 2,
            box[1] + box[3] // 2,
            60,
        )
        time.sleep(2.5)
        return True

    try:
        if try_claim_on_current_page():
            print("[听书领取] 已点领取", flush=True)
            return True
        # 回书架
        s = client.screencap()
        if not any(t.strip() == "书架" and b[1] < 100 for t, b in ocr()):
            client.swipe(89, 1263, 89, 1263, 60)
            time.sleep(2.5)
        # 点时长兑赠币入口
        s = client.screencap()
        entry = [(t, b) for t, b in ocr() if "兑赠币" in t or "领20赠币" in t]
        if not entry:
            print("[听书领取] 未找到奖励入口", flush=True)
            return False
        t, b = entry[-1]
        client.swipe(b[0] + b[2] // 2, b[1] + b[3] // 2, b[0] + b[2] // 2, b[1] + b[3] // 2, 60)
        time.sleep(4)
        # 下滑找听书卡「立即领取」
        for _ in range(5):
            if try_claim_on_current_page():
                print("[听书领取] 已点领取", flush=True)
                return True
            client.swipe(360, 1100, 360, 600, 450)
            time.sleep(1.8)
        print("[听书领取] 未找到听书卡领取按钮（可能已领）", flush=True)
        return False
    finally:
        client.close()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-reading", action="store_true")
    ap.add_argument("--skip-audiobook", action="store_true")
    ap.add_argument("--skip-game", action="store_true")
    ap.add_argument("--skip-ad", action="store_true")
    ap.add_argument("--game-minutes", type=int, default=22,
                    help="游戏挂机时长（22 分钟含结算缓冲，服务器按 20 分钟档计）")
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

    if not plan:
        print("没有需要执行的任务。")
        return 0

    snapshots = tuple(
        FlowStepSnapshot.create(
            step_id=f"{index:02d}-{task}",
            task_key=task,
            display_name=task,
            settings={
                item[2:]: extra[position + 1]
                for position, item in enumerate(extra)
                if item.startswith("--") and position + 1 < len(extra)
            },
        )
        for index, (task, extra) in enumerate(plan, start=1)
    )
    flow = DailyFlowRun.start(snapshots, config_path=str(CONFIG.resolve()))
    recorder = DailyFlowRecorder(ROOT / "runtime" / "records")
    record_path = recorder.save(flow)
    print(
        f"[流水线] run={flow.run_id} 业务日={flow.business_day} "
        f"记录={record_path}",
        flush=True,
    )

    results: list[tuple[str, bool, float]] = []
    try:
        for task, extra in plan:
            ok, dt = run(task, extra)
            results.append((task, ok, dt))
            flow.complete_current(
                0 if ok else 2,
                reason="任务证据确认成功" if ok else "run_task.py 返回非零退出码",
            )
            recorder.save(flow)
            if task == "DailyAudiobookFlow" and ok:
                try:
                    claim_audiobook_reward()
                except Exception as exc:
                    print(f"[听书领取] 异常: {exc}", flush=True)
            if flow.state is FlowRunState.RUNNING:
                flow.start_next()
                recorder.save(flow)
                time.sleep(5)  # 当前任务完整结束后才进入下一项
    except KeyboardInterrupt:
        if flow.state is FlowRunState.RUNNING:
            flow.stop_by_user(reason="命令行用户中断流水线")
            recorder.save(flow)
        print("\n[流水线] 已停止；当前任务取消，后续任务跳过。", flush=True)
        return 130

    print("\n===== 汇总 =====")
    duration_by_task = {task: dt for task, _ok, dt in results}
    for step in flow.steps:
        duration = duration_by_task.get(step.snapshot.task_key, 0.0)
        print(f"{step.state.value:<10} {step.snapshot.task_key} ({duration:.0f}s)")
    print(f"流水线状态：{flow.state.value}")
    print(f"流水线记录：{record_path}")
    return 0 if flow.state is FlowRunState.SUCCEEDED else 1


if __name__ == "__main__":
    raise SystemExit(main())
