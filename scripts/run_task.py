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
from qqreader.errors import ContractViolation
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
from qqreader.runner.retry import BackoffPolicy, RetryExhaustedError, run_with_retry
from qqreader.runner.runner import RunnerConfig, TaskRunner
from qqreader.runtime.clock import RealClock
from qqreader.tasks.ad import AD_TASK_NAME, build_ad_definition
from qqreader.tasks.game import GAME_TASK_NAME, build_game_definition

import logging

from qqreader.contract.outcome import TaskOutcome
from qqreader.maa.adb import run_adb
from qqreader.maa.client import MaaClientError
from qqreader.runner.gui_observability import (
    DeviceScreencapGuard,
    setup_task_file_logging,
    write_failure_record,
)

_LOG = logging.getLogger("qqreader.task")

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
    parser.add_argument(
        "--max-retries",
        type=int,
        default=3,
        help="可重试瞬断错误的最大重试次数",
    )
    parser.add_argument("--quiet", action="store_true")
    return parser


def _build_runtime(client: Any, *, verbose: bool):
    keys = DEFAULT_FEATURE_KEYS
    catalog = FeatureCatalog.from_feature_keys(
        keys,
        rois={"game_ocr_online_play": (0, 800, 720, 1280)},
    )
    observer = DeviceScreencapGuard(
        LoggingObserver(
            MaaPageObserver(
                client, catalog, target_package=keys.qq_reader_package
            ),
            verbose=verbose,
        ),
        log=_retry_log,
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


def _retry_log(message: str) -> None:
    print(f"[retry] {message}", flush=True)


def run_device_preflight(client, config, policy, *, adb_probe=run_adb, log=None):
    """Start-before-run device smoke preflight (issue #12). Returns (ok, detail)."""
    _log = log if log is not None else (lambda m: None)
    result = adb_probe(config.machine.adb_path, "devices", timeout=15.0)
    listed = result is not None and config.machine.adb_address in (result.stdout or "")
    if not listed:
        output = (
            (result.stdout or "").strip() if result is not None else "<adb call failed>"
        )
        return (
            False,
            "adb devices 未列出设备 " + config.machine.adb_address
            + "（输出: " + output + "）；请确认模拟器已启动、配置里的 adb 地址正确，"
            "或重启 adb（adb kill-server && adb start-server）后重试",
        )
    run_with_retry(client.connect, policy, log=_retry_log)
    try:
        shot = client.screencap()
    except Exception as exc:  # noqa: BLE001 - 预检把任何截屏异常转为可读失败详情
        return (
            False,
            "冒烟截屏失败 " + type(exc).__name__ + ": " + str(exc)
            + "；adb 在线不代表截屏可用，请检查模拟器画面/重启模拟器后重试",
        )
    return (
        True,
        "冒烟截屏正常 " + str(getattr(shot, "width", "?"))
        + "x" + str(getattr(shot, "height", "?")),
    )


def _main(args: argparse.Namespace, policy: BackoffPolicy, config: Any) -> int:
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
        # 设备冒烟预检（issue #12）：adb 列设备 + 连接 + 一次截屏，失败则任务不启动。
        preflight_ok, preflight_detail = run_device_preflight(client, config, policy)
        _LOG.info("preflight: %s", preflight_detail)
        print("[preflight] " + preflight_detail, flush=True)
        if not preflight_ok:
            started = time.time()
            path = write_failure_record(
                Path(config.machine.record_dir),
                Path(config.machine.screenshot_dir),
                args.task,
                TaskOutcome.DEVICE_ERROR,
                "设备冒烟预检失败: " + preflight_detail,
                started_at=started,
                ended_at=time.time(),
                device_error=preflight_detail,
            )
            print("[outcome] DEVICE_ERROR", flush=True)
            print("[reason] 设备冒烟预检失败，任务未启动: " + preflight_detail, flush=True)
            if path:
                print("[record] " + str(path), flush=True)
            return 3
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
        # 任务主循环可能因瞬断中断：整体退避重试，每次重试重建 runner。
        run_started = time.time()
        try:
            result = run_with_retry(
                lambda: TaskRunner(
                    definition,
                    RealClock(),
                    config=RunnerConfig(max_steps=args.max_steps),
                    recorder=recorder,
                ).run(),
                policy,
                log=_retry_log,
            )
        except RetryExhaustedError as exc:
            path = write_failure_record(
                Path(config.machine.record_dir),
                Path(config.machine.screenshot_dir),
                args.task,
                TaskOutcome.DEVICE_ERROR,
                "设备/链路瞬断重试耗尽: " + str(exc.last_error),
                started_at=run_started,
                ended_at=time.time(),
                device_error=str(exc.last_error),
            )
            if path:
                print("[record] " + str(path), flush=True)
            _LOG.error("retry exhausted: %s", exc)
            raise
        except MaaClientError as exc:
            path = write_failure_record(
                Path(config.machine.record_dir),
                Path(config.machine.screenshot_dir),
                args.task,
                TaskOutcome.DEVICE_ERROR,
                "MAA 设备级错误（截屏链路不可用）: " + str(exc),
                started_at=run_started,
                ended_at=time.time(),
                device_error=str(exc),
            )
            if path:
                print("[record] " + str(path), flush=True)
            _LOG.error("maa client error: %s", exc)
            raise
        except Exception as exc:
            path = write_failure_record(
                Path(config.machine.record_dir),
                Path(config.machine.screenshot_dir),
                args.task,
                TaskOutcome.FAILED,
                "未预期异常: " + type(exc).__name__ + ": " + str(exc),
                started_at=run_started,
                ended_at=time.time(),
                device_error="",
            )
            if path:
                print("[record] " + str(path), flush=True)
            _LOG.error("unexpected failure: %s: %s", type(exc).__name__, exc)
            raise
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


# 退出码语义：0=成功；2=瞬断重试耗尽；3=致命错误/未预期异常。
# （2 同时保留 run_task 原有的「任务未成功 / 参数配置错误」失败路径。）
def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _build_parser().parse_args(argv)
    setup_task_file_logging(_ROOT / "runtime" / "logs", args.task)
    _LOG.info("task start argv=%s", " ".join(sys.argv[1:]))
    try:
        policy = BackoffPolicy(max_retries=args.max_retries)
        # 配置缺失等致命错误由 is_retryable 判定为不可重试，直接上抛。
        config = run_with_retry(
            lambda: load_config(args.config), policy, log=_retry_log
        )
        return _main(args, policy, config)
    except RetryExhaustedError as exc:
        print("[outcome] DEVICE_ERROR", flush=True)
        print(
            f"[reason] 设备/链路瞬断重试耗尽：共尝试 {exc.attempts} 次仍失败：{exc.last_error}",
            flush=True,
        )
        print(f"[error] {type(exc.last_error).__name__}: {exc.last_error}", flush=True)
        _LOG.error("retry exhausted: %s", exc)
        return 2
    except MaaClientError as exc:
        print("[outcome] DEVICE_ERROR", flush=True)
        print(
            f"[reason] MAA 设备级错误（截屏链路不可用）: {exc}；请检查模拟器/重启 adb 后重试",
            flush=True,
        )
        _LOG.error("maa client error: %s", exc)
        return 3
    except ContractViolation as exc:
        print("[outcome] fatal_contract_violation", flush=True)
        print(f"[reason] 违反运行契约，任务终止: {exc}", flush=True)
        _LOG.error("contract violation: %s", exc)
        return 3
    except FileNotFoundError as exc:
        print("[outcome] fatal_config_missing", flush=True)
        print(f"[reason] 配置文件缺失或路径不可达: {exc}", flush=True)
        _LOG.error("config missing: %s", exc)
        return 3
    except Exception as exc:
        print("[outcome] unexpected_failure", flush=True)
        print(f"[reason] 未预期异常，任务终止: {type(exc).__name__}: {exc}", flush=True)
        _LOG.error("unexpected failure: %s: %s", type(exc).__name__, exc)
        return 3


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
