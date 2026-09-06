"""Run one MaaFramework task entry against the QQ Reader MuMu emulator.

This is a direct MaaFramework runner (no MaaPiCli).  It creates an ADB
controller to the configured MuMu instance, loads the QQ Reader resource bundle,
and posts a pipeline entry such as ``DailyAdFlow``.  The supervisor
``run_ad_with_captcha.py`` can launch this in the background and watch
``maafw.log`` for CAPTCHA / ad-entry events while Maa executes the pipeline.
"""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import sys
import time
from pathlib import Path

STATUS_SUCCEEDED = 3000
PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _b(value: str | Path) -> bytes:
    return os.fsencode(os.fspath(value))


class MaaTaskRunner:
    def __init__(self, runtime: Path, resource: Path, adb: Path,
                 device: str, log_dir: Path) -> None:
        self.runtime = runtime
        self.resource_path = resource
        self.adb = adb
        self.device = device
        self.log_dir = log_dir
        self._dll_dir = os.add_dll_directory(str(runtime))
        self.lib = ctypes.CDLL(str(runtime / "MaaFramework.dll"))
        self.resource = ctypes.c_void_p()
        self.controller = ctypes.c_void_p()
        self.tasker = ctypes.c_void_p()
        self._configure_api()

    def _configure_api(self) -> None:
        lib = self.lib
        lib.MaaVersion.restype = ctypes.c_char_p
        lib.MaaGlobalSetOption.argtypes = [ctypes.c_int32, ctypes.c_void_p,
                                           ctypes.c_uint64]
        lib.MaaGlobalSetOption.restype = ctypes.c_uint8
        lib.MaaResourceCreate.restype = ctypes.c_void_p
        lib.MaaResourcePostBundle.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
        lib.MaaResourcePostBundle.restype = ctypes.c_int64
        lib.MaaResourceWait.argtypes = [ctypes.c_void_p, ctypes.c_int64]
        lib.MaaResourceWait.restype = ctypes.c_int32
        lib.MaaResourceDestroy.argtypes = [ctypes.c_void_p]
        lib.MaaAdbControllerCreate.argtypes = [
            ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint64, ctypes.c_uint64,
            ctypes.c_char_p, ctypes.c_char_p]
        lib.MaaAdbControllerCreate.restype = ctypes.c_void_p
        lib.MaaControllerSetOption.argtypes = [
            ctypes.c_void_p, ctypes.c_int32, ctypes.c_void_p, ctypes.c_uint64]
        lib.MaaControllerSetOption.restype = ctypes.c_uint8
        lib.MaaControllerPostConnection.argtypes = [ctypes.c_void_p]
        lib.MaaControllerPostConnection.restype = ctypes.c_int64
        lib.MaaControllerWait.argtypes = [ctypes.c_void_p, ctypes.c_int64]
        lib.MaaControllerWait.restype = ctypes.c_int32
        lib.MaaControllerDestroy.argtypes = [ctypes.c_void_p]
        lib.MaaTaskerCreate.restype = ctypes.c_void_p
        lib.MaaTaskerBindResource.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        lib.MaaTaskerBindResource.restype = ctypes.c_uint8
        lib.MaaTaskerBindController.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        lib.MaaTaskerBindController.restype = ctypes.c_uint8
        lib.MaaTaskerPostTask.argtypes = [ctypes.c_void_p, ctypes.c_char_p,
                                          ctypes.c_char_p]
        lib.MaaTaskerPostTask.restype = ctypes.c_int64
        lib.MaaTaskerWait.argtypes = [ctypes.c_void_p, ctypes.c_int64]
        lib.MaaTaskerWait.restype = ctypes.c_int32
        lib.MaaTaskerDestroy.argtypes = [ctypes.c_void_p]

    def run(self, entry: str) -> dict[str, object]:
        self.log_dir.mkdir(parents=True, exist_ok=True)
        log_value = _b(self.log_dir)
        log_buffer = ctypes.create_string_buffer(log_value)
        self.lib.MaaGlobalSetOption(
            1, ctypes.cast(log_buffer, ctypes.c_void_p), len(log_value))

        self.resource = ctypes.c_void_p(self.lib.MaaResourceCreate())
        if not self.resource.value:
            raise RuntimeError("MaaResourceCreate failed")
        resource_id = self.lib.MaaResourcePostBundle(
            self.resource, _b(self.resource_path))
        resource_status = self.lib.MaaResourceWait(self.resource, resource_id)
        if resource_status != STATUS_SUCCEEDED:
            raise RuntimeError(f"MAA resource load failed: {resource_status}")

        # MuMu uses its own ADB server on 5038.
        os.environ["ANDROID_ADB_SERVER_PORT"] = "5038"
        self.controller = ctypes.c_void_p(self.lib.MaaAdbControllerCreate(
            _b(self.adb), self.device.encode("utf-8"),
            1 << 1, 1, b"{}", _b(self.runtime / "MaaAgentBinary")))
        if not self.controller.value:
            raise RuntimeError("MaaAdbControllerCreate failed")
        short_side = ctypes.c_int32(720)
        self.lib.MaaControllerSetOption(
            self.controller, 2, ctypes.byref(short_side),
            ctypes.sizeof(short_side))
        conn_id = self.lib.MaaControllerPostConnection(self.controller)
        status = self.lib.MaaControllerWait(self.controller, conn_id)
        if status != STATUS_SUCCEEDED:
            raise RuntimeError(f"MAA controller connection failed: {status}")

        self.tasker = ctypes.c_void_p(self.lib.MaaTaskerCreate())
        if not self.tasker.value:
            raise RuntimeError("MaaTaskerCreate failed")
        if not self.lib.MaaTaskerBindResource(self.tasker, self.resource):
            raise RuntimeError("MaaTaskerBindResource failed")
        if not self.lib.MaaTaskerBindController(self.tasker, self.controller):
            raise RuntimeError("MaaTaskerBindController failed")
        task_id = self.lib.MaaTaskerPostTask(
            self.tasker, entry.encode("utf-8"), b"{}")
        task_status = self.lib.MaaTaskerWait(self.tasker, task_id)
        return {
            "success": task_status == STATUS_SUCCEEDED,
            "status": task_status,
            "entry": entry,
            "framework_version": self.lib.MaaVersion().decode("utf-8", "replace"),
            "device": self.device,
        }

    def close(self) -> None:
        if self.tasker.value:
            self.lib.MaaTaskerDestroy(self.tasker)
            self.tasker = ctypes.c_void_p()
        if self.controller.value:
            self.lib.MaaControllerDestroy(self.controller)
            self.controller = ctypes.c_void_p()
        if self.resource.value:
            self.lib.MaaResourceDestroy(self.resource)
            self.resource = ctypes.c_void_p()
        try:
            self._dll_dir.close()
        except Exception:
            pass


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("entry", nargs="?", default="DailyAdFlow")
    parser.add_argument("--runtime", type=Path,
                        default=PROJECT_ROOT / "dev")
    parser.add_argument("--resource", type=Path,
                        default=PROJECT_ROOT / "dev" / "resource")
    parser.add_argument("--adb", type=Path,
                        default=Path(r"D:\Program Files\Netease\MuMu Player 12\shell\adb.exe"))
    parser.add_argument("--device", default="127.0.0.1:16385")
    parser.add_argument("--log-dir", type=Path,
                        default=PROJECT_ROOT / "dev" / "debug")
    args = parser.parse_args()

    runner = MaaTaskRunner(args.runtime, args.resource, args.adb,
                           args.device, args.log_dir)
    try:
        result = runner.run(args.entry)
    except Exception as exc:
        result = {"success": False, "entry": args.entry, "error": str(exc)}
    finally:
        runner.close()
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result.get("success") else 2


if __name__ == "__main__":
    raise SystemExit(main())
