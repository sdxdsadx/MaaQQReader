"""看广告 12 层监督循环（用户指令 2026-09-11）。

策略:
- 循环跑 DailyAdFlow（每轮 40min 上限， runner 内部会连续看完多个广告）
- 每轮结束解析日志中的「(N/12)」进度 + records 的 outcome
- 进度有增长（N 变大）→ 继续下一轮（接着看剩余层数）
- 进度滞留（连续 2 轮 N 不变或拿不到）→ 按用户指令: 提 issue → 重跑
- N == 12 或「看小视频…明日再来」→ 任务完成，退出

用法: python scripts/supervise_ads.py
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = r"D:\python\python.exe"
RECORDS = ROOT / "runtime" / "records"
LOGS = ROOT / "runtime" / "logs"
REPO = "sdxdsadx/MaaQQReader"

MAX_ROUNDS = 12
STALL_LIMIT = 2


def parse_progress(log_path: Path) -> int | None:
    """从一轮日志提取最大广告进度 N（来自「获得1个礼物(N/12)」）。"""
    try:
        text = log_path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None
    nums = [int(m.group(1)) for m in re.finditer(r"(\d+)\s*/\s*12", text)]
    return max(nums) if nums else None


def has_ad_done(text: str) -> bool:
    """广告卡完成后文案（与游戏卡「明日再来」区分，要求看视频上下文）。"""
    return bool(re.search(r"(看小视频|看视频).{0,40}(明日再来|已领取|已领完)", text))


def latest_record() -> Path | None:
    files = sorted(RECORDS.glob("DailyAdFlow_*.json"), key=lambda p: p.stat().st_mtime)
    return files[-1] if files else None


def record_outcome(path: Path | None) -> str:
    if path is None:
        return "no-record"
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
        return str(data.get("outcome", "unknown"))
    except (OSError, json.JSONDecodeError):
        return "unreadable"


def run_once(idx: int) -> Path:
    log = LOGS / f"supervise_r{idx}.log"
    cmd = (
        f'"{PY}" scripts\\run_task.py --config configs\\qqreader.local.json '
        f"--task DailyAdFlow --timeout-minutes 40"
    )
    with open(log, "w", encoding="utf-8") as fh:
        subprocess.run(cmd, shell=True, stdout=fh, stderr=fh, cwd=str(ROOT), timeout=42 * 60)
    return log


def create_issue(title: str, body: str) -> str | None:
    for attempt in range(4):
        r = subprocess.run(
            ["gh", "issue", "create", "--repo", REPO, "--title", title, "--body", body],
            capture_output=True, text=True, cwd=str(ROOT), timeout=120,
        )
        if r.returncode == 0:
            return (r.stdout or "").strip()
        time.sleep(6 * (attempt + 1))
    return None


def log_tail(log: Path, lines: int = 4) -> str:
    try:
        rows = log.read_text(encoding="utf-8", errors="ignore").splitlines()[-lines:]
        return " | ".join(r[-100:] for r in rows)
    except OSError:
        return "(no log)"


def main() -> int:
    print(f"[supervise] start rounds={MAX_ROUNDS} stall_limit={STALL_LIMIT}", flush=True)
    best = 0
    stall = 0
    issues_filed = []
    for rnd in range(1, MAX_ROUNDS + 1):
        t0 = time.time()
        try:
            log = run_once(rnd)
        except subprocess.TimeoutExpired:
            print(f"[round {rnd}] run_task 强杀（42min 保护）", flush=True)
            log = LOGS / f"supervise_r{rnd}.log"
        dur = int((time.time() - t0) / 60)
        prog = parse_progress(log)
        outcome = record_outcome(latest_record())
        done = has_ad_done(log.read_text(encoding="utf-8", errors="ignore"))
        print(
            f"[round {rnd}] outcome={outcome} progress={prog} "
            f"ad_done={done} {dur}min", flush=True,
        )

        if outcome == "SUCCESS" or done or (prog is not None and prog >= 12):
            print(f"[supervise] ✅ 12 层达成（progress={prog} outcome={outcome}）", flush=True)
            return 0

        if prog is not None and prog > best:
            best = prog
            stall = 0
            print(f"[supervise] 进度推进 {best}/12，继续", flush=True)
            continue

        # 滞留判定
        stall += 1
        print(f"[supervise] 进度滞留（stall={stall}/{STALL_LIMIT} best={best}）", flush=True)
        if stall >= STALL_LIMIT:
            title = f"[ads-watch] 看广告进度滞留 {best}/12（第{rnd}轮 outcome={outcome}）"
            body = (
                f"## 现象\n"
                f"- 第 {rnd} 轮 DailyAdFlow 结束，outcome={outcome}，进度滞留在 {best}/12\n"
                f"- 连续 {stall} 轮无进度增长（监督阈值 {STALL_LIMIT}）\n\n"
                f"## 证据\n"
                f"- 日志: runtime/logs/supervise_r{rnd}.log\n"
                f"- 尾部: {log_tail(log)}\n\n"
                f"## 判断\n"
                f"疑似随机到未解决广告类型（目前仅信息流/视频两类已解决，"
                f"拉活/直播间等其他类型会循环或静默失败）。\n\n"
                f"## 监督动作\n"
                f"按预案重跑看广告流程，直到随机到已解决类型跑满 12 层。"
            )
            url = create_issue(title, body)
            print(f"[supervise] issue 提交: {url or 'FAILED(gh)'}", flush=True)
            if url:
                issues_filed.append(url)
            stall = 0
    print(f"[supervise] 达到最大轮数 {MAX_ROUNDS}，best={best}/12", flush=True)
    return 1 if best < 12 else 0


if __name__ == "__main__":
    sys.exit(main())
