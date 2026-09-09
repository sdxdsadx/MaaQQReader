"""通用单任务运行器：支持新流程任务与旧 GUI 迁移任务。

GUI 串行执行每个任务时调用本脚本；也可以单独命令行使用。
"""

from __future__ import annotations

import argparse
import json
import subprocess
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

LEGACY_ENTRY = {
    "DailyReadingFlow": "DirectReadingFlow",
    "DailyAudiobookFlow": "DailyAudiobookFlow",
    "DailyExternalAppFlow": "DailyExternalAppFlow",
    "DailyLevelAdFlow": "DailyLevelAdFlow",
    "ClaimOneReward": "ClaimOneReward",
}
LEGACY_TIMING_NODE = {
    "DailyReadingFlow": "ReadingWaitOneMinute",
    "DailyAudiobookFlow": "AudiobookWaitOneMinute",
}


def _find_legacy_runner(repo_root: Path) -> Optional[Path]:
    for candidate in sorted(repo_root.glob("_backup_old_project_*/tools/run_maa_ad.py")):
        if candidate.is_file():
            return candidate
    return None


def _patch_legacy_pipeline(resource_dir: Path, node: str, minutes: float):
    pipeline_path = resource_dir / "pipeline" / "qq_reader_trial.json"
    if not pipeline_path.is_file():
        return None
    original = pipeline_path.read_bytes()
    try:
        data = json.loads(original.decode("utf-8"))
        if node in data:
            data[node]["post_delay"] = int(float(minutes) * 60000)
            pipeline_path.write_text(
                json.dumps(data, ensure_ascii=False, indent=4) + "\n",
                encoding="utf-8",
            )
        return original
    except (OSError, ValueError) as exc:
        print(f"[legacy] 修改旧 pipeline 失败: {exc}", flush=True)
        return None


def _run_legacy_task(task: str, config: Any, minutes: Optional[float]) -> int:
    repo_root = Path(__file__).resolve().parents[1]
    runner = _find_legacy_runner(repo_root)
    if runner is None:
        print(
            "[legacy] 找不到旧 run_maa_ad.py（应在 _backup_old_project_*/tools/）",
            flush=True,
        )
        return 3
    entry = LEGACY_ENTRY.get(task, task)
    node = LEGACY_TIMING_NODE.get(task)
    original = None
    resource_dir = Path(config.machine.maa_resource_dir)
    from qqreader.maa.adb import ensure_maa_ready

    ready, detail = ensure_maa_ready(
        config.machine.adb_path,
        config.machine.adb_address,
        package_name=config.machine.package_name,
        timeout=45.0,
    )
    print(f"[legacy] ADB 预检: {detail}", flush=True)
    if not ready:
        print("[legacy] 设备不可截图，旧流程可能仍会失败。", flush=True)
    if node and minutes and float(minutes) > 0:
        original = _patch_legacy_pipeline(resource_dir, node, float(minutes))
    command = [
        sys.executable,
        str(runner),
        entry,
        "--runtime",
        str(config.machine.maa_runtime_dir),
        "--resource",
        str(resource_dir),
        "--adb",
        str(config.machine.adb_path),
        "--device",
        str(config.machine.adb_address),
        "--log-dir",
        str(config.machine.log_dir),
    ]
    print("[legacy] 调用旧 QQ 阅读流程: " + " ".join(command), flush=True)
    try:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if process.stdout is not None:
            for line in process.stdout:
                print(line.rstrip(), flush=True)
        return process.wait()
    except OSError as exc:
        print(f"[legacy] 启动旧流程失败: {exc}", flush=True)
        return 3
    finally:
        if original is not None:
            pipeline_path = resource_dir / "pipeline" / "qq_reader_trial.json"
            try:
                pipeline_path.write_bytes(original)
            except OSError:
                pass


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
    config = load_config(args.config)

    if args.task in LEGACY_NOT_IMPLEMENTED:
        minutes = args.minutes if args.minutes is not None else args.duration_minutes
        return _run_legacy_task(args.task, config, minutes)

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
