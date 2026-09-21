"""读取当前奖励页，保存动态 GUI 计划；--run 按该计划串行执行。"""
import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from qqreader.config import load_config
from qqreader.maa.factory import build_maa_client
from qqreader.gui.dynamic_plan import collect_cards, plan_from_cards
from qqreader.gui.task_catalog import build_serial_plan, save_task_settings
from qqreader.gui.commands import build_run_task_command


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--run", action="store_true")
    args = parser.parse_args()
    directory = ROOT / "runtime" / "dynamic_plan" / datetime.now().strftime("%Y%m%d_%H%M%S")
    client = build_maa_client(load_config(args.config))
    try:
        client.connect()
        cards, pages = collect_cards(client, directory)
    finally:
        client.close()
    settings, notes = plan_from_cards(cards)
    report = {"cards": cards, "pages": pages, "notes": notes}
    (directory / "evidence.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    order = ["ClaimAudiobookReward", "ClaimOneReward", "DailyGameFlow", "DailyAdFlow", "DailyLevelAdFlow", "DailyAudiobookFlow", "DailyReadingFlow"]
    save_task_settings(ROOT / "runtime" / "gui_tasks.json", settings, order=order)
    print("\n".join(notes), flush=True)
    print(f"证据：{directory}", flush=True)
    if args.run:
        for step in build_serial_plan(settings, order=order):
            command = build_run_task_command(sys.executable, ROOT, Path(args.config), step.spec.key, settings=step.settings.values)
            print(f"开始：{step.spec.key} {step.settings.values}", flush=True)
            result = subprocess.run(command, cwd=ROOT)
            print(f"结束：{step.spec.key} exit={result.returncode}", flush=True)
            if result.returncode:
                return result.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
