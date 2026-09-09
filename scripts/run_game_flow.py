"""Run ``DailyGameFlow`` against MaaFramework with live observation logs.

Usage::

    py -3.10 scripts/run_game_flow.py --config configs/qqreader.local.json
    py -3.10 scripts/run_game_flow.py --config ... --duration-minutes 0.02  # dry run
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Optional, Sequence

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# Windows 控制台默认 GBK，OCR 文本可能包含无法编码的字符；显式改 UTF-8，
# 否则 print 会抛 UnicodeEncodeError 并被 TaskRunner 记成任务失败。
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
from qqreader.tasks.game import build_game_definition


class LoggingObserver:
    """把每次观测的 OCR / App / 方向写到 stdout，便于监督运行。"""

    def __init__(self, inner: Any, *, verbose: bool = True) -> None:
        self._inner = inner
        self._verbose = verbose
        self.count = 0

    def observe(self, context: Any, *, deep: bool = False) -> Any:
        observation = self._inner.observe(context, deep=deep)
        self.count += 1
        if self._verbose:
            ocr = list(observation.ocr_texts[:12])
            print(
                f"[observe {self.count}] app={observation.current_app} "
                f"orientation={observation.orientation.value} ocr={ocr}",
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
        prog="python scripts/run_game_flow.py",
        description="运行 DailyGameFlow（游戏大厅 → 在线玩 → 游戏 → 领币 → 退出 → 奖励页）",
    )
    parser.add_argument("--config", required=True, help="QQReader 配置 JSON/YAML")
    parser.add_argument(
        "--duration-minutes",
        type=float,
        default=22.0,
        help="游戏挂机时长（分钟），默认 22；干跑可传 0.02",
    )
    parser.add_argument(
        "--timeout-minutes",
        type=float,
        default=30.0,
        help="任务独立超时（分钟），默认 30",
    )
    parser.add_argument("--max-steps", type=int, default=2000)
    parser.add_argument("--quiet", action="store_true", help="不打印每次观测")
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
            # 「在线玩」顶部 tab 在 y≈150；游戏卡按钮在下半屏。限定 ROI，
            # 避免 OCR 定位到不可点击的顶部 tab。
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
        recorder = FileRunRecorder(
            RecordingConfig(
                record_dir=config.machine.record_dir,
                screenshot_dir=config.machine.screenshot_dir,
                retention_days=30,
            )
        )
        definition = build_game_definition(
            keys,
            observer,
            device,
            EscalationPolicy(),
            recognizer,
            timeout_seconds=args.timeout_minutes * 60.0,
            game_duration_seconds=args.duration_minutes * 60.0,
        )
        print(
            f"[run] DailyGameFlow duration={args.duration_minutes:g}min "
            f"timeout={args.timeout_minutes:g}min",
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
        for event in result.diagnostics[-80:]:
            print("  " + event.render(), flush=True)
        return 0 if result.succeeded else 2
    finally:
        client.close()


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
