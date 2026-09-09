"""通用单任务运行器：``--task DailyGameFlow|DailyAdFlow``。

GUI 串行执行每个任务时调用本脚本；也可以单独命令行使用。
"""

from __future__ import annotations

import argparse
import sys
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

TASK_NAMES = (GAME_TASK_NAME, AD_TASK_NAME)


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
    parser.add_argument("--duration-minutes", type=float, default=22.0)
    parser.add_argument("--timeout-minutes", type=float, default=30.0)
    parser.add_argument("--max-steps", type=int, default=2000)
    parser.add_argument("--quiet", action="store_true")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.duration_minutes <= 0:
        print("[配置错误] --duration-minutes 必须 > 0", file=sys.stderr)
        return 2
    if args.timeout_minutes <= 0:
        print("[配置错误] --timeout-minutes 必须 > 0", file=sys.stderr)
        return 2

    config = load_config(args.config)
    client = build_maa_client(config)
    try:
        client.connect()
        keys = DEFAULT_FEATURE_KEYS
        catalog = FeatureCatalog.from_feature_keys(
            keys,
            rois={"game_ocr_online_play": (0, 800, 720, 1280)},
        )
        observer = LoggingObserver(
            MaaPageObserver(
                client, catalog, target_package=keys.qq_reader_package
            ),
            verbose=not args.quiet,
        )
        locator = MaaFeatureLocator(client, catalog, observer=observer)
        device = MaaDeviceController(client, locator)
        recognizer = PageStateRecognizer(build_default_state_definitions(keys))
        recovery = EscalationPolicy()
        if args.task == GAME_TASK_NAME:
            definition = build_game_definition(
                keys,
                observer,
                device,
                recovery,
                recognizer,
                timeout_seconds=args.timeout_minutes * 60.0,
                game_duration_seconds=args.duration_minutes * 60.0,
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
            f"duration={args.duration_minutes:g}min",
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
