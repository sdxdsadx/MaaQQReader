"""通用单任务运行器：支持新流程任务与旧 GUI 迁移任务。

GUI 串行执行每个任务时调用本脚本；也可以单独命令行使用。
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Any, Optional, Sequence

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

for _stream in (sys.stdout, sys.stderr):
    reconfigure = getattr(_stream, "reconfigure", None)
    if reconfigure is not None:
        reconfigure(encoding="utf-8", errors="replace")

from qqreader.config import load_config
from qqreader.maa.catalog import FeatureCatalog
from qqreader.maa.device import MaaDeviceController
from qqreader.maa.factory import build_maa_client
from qqreader.maa.locator import MaaFeatureLocator
from qqreader.maa.observer import MaaPageObserver
from qqreader.page.feature_keys import DEFAULT_FEATURE_KEYS
from qqreader.page.profiles import build_default_state_definitions
from qqreader.page.recognizer import PageStateRecognizer
from qqreader.recovery.policy import EscalationPolicy
from qqreader.runner.recording import FileRunRecorder, RecordingConfig
from qqreader.runner.runner import RunnerConfig, TaskRunner
from qqreader.runtime.clock import RealClock
from qqreader.tasks.ad import AD_TASK_NAME, build_ad_definition
from qqreader.tasks.game import GAME_TASK_NAME, build_game_definition

SYSTEM_TASKS = ("LaunchQQReader", "SmokeTest")
NEW_FLOW_TASKS = (GAME_TASK_NAME, AD_TASK_NAME)
LEGACY_NOT_IMPLEMENTED = (
    "DailyReadingFlow",
    "DailyAudiobookFlow",
    "DailyExternalAppFlow",
    "DailyLevelAdFlow",
    "ClaimOneReward",
)
TASK_NAMES = NEW_FLOW_TASKS + SYSTEM_TASKS + LEGACY_NOT_IMPLEMENTED


class LoggingObserver:
    def __init__(self, inner: Any, *, verbose: bool = True) -> None:
        self._inner = inner
        self._verbose = verbose
        self.count = 0

    def observe(self, context: Any, *, deep: bool = False) -> Any:
        observation = self._inner.observe(context, deep=deep)
        self.count += 1
        if self._verbose:
            print(
                f"[observe {self.count}] app={observation.current_app} "
                f"orientation={observation.orientation.value} "
                f"ocr={list(observation.ocr_texts[:12])}",
                flush=True,
            )
        return observation

    def save_last_screenshot(self, path: Path) -> Optional[Path]:
        return self._inner.save_last_screenshot(path)

    @property
    def last_screenshot(self) -> Any:
        return getattr(self._inner, "last_screenshot", None)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python scripts/run_task.py",
        description="运行单个 QQReader 任务（供 GUI 串行执行）",
    )
    parser.add_argument("--config", required=True)
    parser.add_argument("--task", required=True, choices=TASK_NAMES)
    parser.add_argument("--duration-minutes", type=float, default=None)
    parser.add_argument("--minutes", type=float, default=None)
    parser.add_argument("--timeout-minutes", type=float, default=30.0)
    parser.add_argument("--max-steps", type=int, default=2000)
    parser.add_argument("--quiet", action="store_true")
    return parser


def _build_runtime(client: Any, *, verbose: bool):
    keys = DEFAULT_FEATURE_KEYS
    catalog = FeatureCatalog.from_feature_keys(
        keys,
        rois={"game_ocr_online_play": (0, 800, 720, 1280)},
    )
    observer = LoggingObserver(
        MaaPageObserver(
            client, catalog, target_package=keys.qq_reader_package
        ),
        verbose=verbose,
    )
    locator = MaaFeatureLocator(client, catalog, observer=observer)
    device = MaaDeviceController(client, locator)
    recognizer = PageStateRecognizer(build_default_state_definitions(keys))
    return keys, observer, device, recognizer


def _run_system_task(
    client: Any,
    task: str,
    *,
    keys: Any,
    observer: Any,
    recognizer: PageStateRecognizer,
) -> int:
    if task == "LaunchQQReader":
        print("[system] 启动 QQ 阅读", flush=True)
        if not client.start_app(keys.qq_reader_package):
            print("[system] start_app 返回失败", file=sys.stderr, flush=True)
            return 2
        time.sleep(3)
    observation = observer.observe(None)
    decision = recognizer.evaluate(observation)
    print(
        f"[system] state={decision.state.value} "
        f"verdict={decision.verdict.value} confidence={decision.confidence:.3f}",
        flush=True,
    )
    print(f"[system] ocr={list(observation.ocr_texts[:20])}", flush=True)
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _build_parser().parse_args(argv)

    if args.task in LEGACY_NOT_IMPLEMENTED:
        print(
            f"[not-implemented] task={args.task} 旧 pipeline 任务尚未接入新状态机；"
            f"已保留在 GUI 任务列表中，请勿把本次运行当作成功。",
            flush=True,
        )
        return 3

    if args.timeout_minutes <= 0:
        print("[配置错误] --timeout-minutes 必须 > 0", file=sys.stderr)
        return 2
    game_duration = args.duration_minutes
    if game_duration is None:
        game_duration = args.minutes
    if args.task == GAME_TASK_NAME:
        if game_duration is None:
            game_duration = 22.0
        if game_duration <= 0:
            print("[配置错误] 游戏挂机分钟必须 > 0", file=sys.stderr)
            return 2

    config = load_config(args.config)
    client = build_maa_client(config)
    try:
        client.connect()
        keys, observer, device, recognizer = _build_runtime(
            client, verbose=not args.quiet
        )
        if args.task in SYSTEM_TASKS:
            return _run_system_task(
                client,
                args.task,
                keys=keys,
                observer=observer,
                recognizer=recognizer,
            )

        recovery = EscalationPolicy()
        if args.task == GAME_TASK_NAME:
            definition = build_game_definition(
                keys,
                observer,
                device,
                recovery,
                recognizer,
                timeout_seconds=args.timeout_minutes * 60.0,
                game_duration_seconds=float(game_duration) * 60.0,
            )
        else:
            definition = build_ad_definition(
                keys,
                observer,
                device,
                recovery,
                recognizer,
                timeout_seconds=args.timeout_minutes * 60.0,
            )
        recorder = FileRunRecorder(
            RecordingConfig(
                record_dir=config.machine.record_dir,
                screenshot_dir=config.machine.screenshot_dir,
                retention_days=30,
            )
        )
        print(
            f"[run] task={args.task} timeout={args.timeout_minutes:g}min "
            f"duration={game_duration if game_duration is not None else '-'}min",
            flush=True,
        )
        result = TaskRunner(
            definition,
            RealClock(),
            config=RunnerConfig(max_steps=args.max_steps),
            recorder=recorder,
        ).run()
        print("[result] " + result.summary(), flush=True)
        print("[outcome] " + result.outcome.value, flush=True)
        print("[reason] " + result.reason, flush=True)
        if result.record_path:
            print("[record] " + result.record_path, flush=True)
        for event in result.diagnostics[-60:]:
            print("  " + event.render(), flush=True)
        return 0 if result.succeeded else 2
    finally:
        client.close()


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
