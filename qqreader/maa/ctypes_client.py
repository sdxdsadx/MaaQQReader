"""真实 MaaFramework 客户端（ctypes，无需 Python 绑定）。

* ``controller="adb"``：通过 ``MaaAdbControllerCreate`` 连接模拟器/真机。
* ``controller="custom"``：通过 ``MaaCustomControllerCreate`` 用 Python 回调
  提供静态截图与记录点击，**无需设备**即可跑通截图 / 识别 / 设备控制全链路
  （用于集成测试与 ``doctor --offline``）。

识别走 ``MaaTaskerPostRecognition``，再按
``MaaTaskerGetTaskDetail → MaaTaskerGetNodeDetail → MaaTaskerGetRecognitionDetail``
取回 ``detail_json``（OCR 为 ``{"all": [...]}``）。
"""

from __future__ import annotations

import ctypes
import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from .client import Box, MaaClientError, RecoResult, Screenshot

STATUS_SUCCEEDED = 3000
OPTION_SCREENSHOT_SHORT_SIDE = 2
OPTION_LOG_DIR = 1
KEYCODE_BACK = 4

MaaBool = ctypes.c_uint8
MaaFeature = ctypes.c_uint64
StringBufferP = ctypes.c_void_p
ImageBufferP = ctypes.c_void_p
RectP = ctypes.c_void_p

_CONNECT = ctypes.CFUNCTYPE(MaaBool, ctypes.c_void_p)
_CONNECTED = ctypes.CFUNCTYPE(MaaBool, ctypes.c_void_p)
_REQUEST_UUID = ctypes.CFUNCTYPE(MaaBool, ctypes.c_void_p, StringBufferP)
_GET_FEATURES = ctypes.CFUNCTYPE(MaaFeature, ctypes.c_void_p)
_START_APP = ctypes.CFUNCTYPE(MaaBool, ctypes.c_char_p, ctypes.c_void_p)
_STOP_APP = ctypes.CFUNCTYPE(MaaBool, ctypes.c_char_p, ctypes.c_void_p)
_SCREENCAP = ctypes.CFUNCTYPE(MaaBool, ctypes.c_void_p, ImageBufferP)
_CLICK = ctypes.CFUNCTYPE(MaaBool, ctypes.c_int32, ctypes.c_int32, ctypes.c_void_p)
_SWIPE = ctypes.CFUNCTYPE(
    MaaBool, ctypes.c_int32, ctypes.c_int32, ctypes.c_int32, ctypes.c_int32, ctypes.c_int32, ctypes.c_void_p
)
_TOUCH_DOWN = ctypes.CFUNCTYPE(
    MaaBool, ctypes.c_int32, ctypes.c_int32, ctypes.c_int32, ctypes.c_int32, ctypes.c_void_p
)
_TOUCH_MOVE = _TOUCH_DOWN
_TOUCH_UP = ctypes.CFUNCTYPE(MaaBool, ctypes.c_int32, ctypes.c_void_p)
_CLICK_KEY = ctypes.CFUNCTYPE(MaaBool, ctypes.c_int32, ctypes.c_void_p)
_INPUT_TEXT = ctypes.CFUNCTYPE(MaaBool, ctypes.c_char_p, ctypes.c_void_p)
_KEY_EVENT = ctypes.CFUNCTYPE(MaaBool, ctypes.c_int32, ctypes.c_void_p)
_SCROLL = ctypes.CFUNCTYPE(MaaBool, ctypes.c_int32, ctypes.c_int32, ctypes.c_void_p)
_RELATIVE_MOVE = ctypes.CFUNCTYPE(MaaBool, ctypes.c_int32, ctypes.c_int32, ctypes.c_void_p)
_SHELL = ctypes.CFUNCTYPE(
    MaaBool, ctypes.c_char_p, ctypes.c_int64, ctypes.c_void_p, StringBufferP
)
_INACTIVE = ctypes.CFUNCTYPE(MaaBool, ctypes.c_void_p)
_GET_INFO = ctypes.CFUNCTYPE(MaaBool, ctypes.c_void_p, StringBufferP)


class MaaCustomControllerCallbacks(ctypes.Structure):
    """与 ``MaaCustomController.h`` 的字段顺序保持一致。"""

    _fields_ = [
        ("connect", _CONNECT),
        ("connected", _CONNECTED),
        ("request_uuid", _REQUEST_UUID),
        ("get_features", _GET_FEATURES),
        ("start_app", _START_APP),
        ("stop_app", _STOP_APP),
        ("screencap", _SCREENCAP),
        ("click", _CLICK),
        ("swipe", _SWIPE),
        ("touch_down", _TOUCH_DOWN),
        ("touch_move", _TOUCH_MOVE),
        ("touch_up", _TOUCH_UP),
        ("click_key", _CLICK_KEY),
        ("input_text", _INPUT_TEXT),
        ("key_down", _KEY_EVENT),
        ("key_up", _KEY_EVENT),
        ("scroll", _SCROLL),
        ("relative_move", _RELATIVE_MOVE),
        ("shell", _SHELL),
        ("inactive", _INACTIVE),
        ("get_info", _GET_INFO),
    ]


@dataclass(frozen=True)
class CtypesMaaConfig:
    """连接 MaaFramework 所需的全部本机参数（来自 ``MachineConfig``）。"""

    runtime_dir: Path
    resource_dir: Optional[Path] = None
    controller: str = "adb"
    adb_path: Optional[str] = None
    adb_address: Optional[str] = None
    package_name: str = "com.qq.reader"
    agent_dir: Optional[Path] = None
    custom_images: Tuple[bytes, ...] = ()
    custom_dir: Optional[Path] = None
    screencap_methods: int = 1 << 1  # MaaAdbScreencapMethod_Encode
    input_methods: int = 1  # MaaAdbInputMethod_AdbShell
    short_side: Optional[int] = None
    log_dir: Optional[Path] = None
    connect_timeout_ms: int = 30000

    def __post_init__(self) -> None:
        object.__setattr__(self, "runtime_dir", Path(self.runtime_dir))
        if self.resource_dir is not None:
            object.__setattr__(self, "resource_dir", Path(self.resource_dir))
        if self.agent_dir is not None:
            object.__setattr__(self, "agent_dir", Path(self.agent_dir))
        if self.custom_dir is not None:
            object.__setattr__(self, "custom_dir", Path(self.custom_dir))
        if self.controller not in ("adb", "custom"):
            raise MaaClientError(f"controller 必须是 'adb' 或 'custom'，当前: {self.controller!r}")
        if self.controller == "adb":
            if not self.adb_path or not self.adb_address:
                raise MaaClientError("controller=adb 需要 adb_path 与 adb_address")
        else:
            if not self.custom_images and self.custom_dir is None:
                raise MaaClientError("controller=custom 需要 custom_images 或 custom_dir")


class _CustomState:
    """自定义控制器的 Python 状态（截图序列 + 调用记录）。"""

    def __init__(self, images: Sequence[bytes]) -> None:
        if not images:
            raise MaaClientError("自定义控制器至少需要一张截图")
        self.images = list(images)
        self.index = 0
        self.calls: List[Tuple[Any, ...]] = []
        self.connected = False
        self.keep_alive: List[Any] = []

    def next_image(self) -> bytes:
        image = self.images[self.index % len(self.images)]
        self.index += 1
        return image


_STATES: Dict[int, _CustomState] = {}
_STATE_IDS = [0]


def _register_state(state: _CustomState) -> int:
    _STATE_IDS[0] += 1
    _STATES[_STATE_IDS[0]] = state
    return _STATE_IDS[0]


def _lookup_state(arg: Any) -> Optional[_CustomState]:
    try:
        key = int(arg) if arg else 0
    except (TypeError, ValueError):
        return None
    return _STATES.get(key)


class CtypesMaaClient:
    """通过 ctypes 调用 ``MaaFramework.dll`` 的客户端。"""

    def __init__(self, config: CtypesMaaConfig, *, clock: Any = None) -> None:
        self._config = config
        self._clock = clock
        self._lib: Any = None
        self._dll_dir: Any = None
        self._resource: Any = ctypes.c_void_p()
        self._controller: Any = ctypes.c_void_p()
        self._tasker: Any = ctypes.c_void_p()
        self._custom_state: Optional[_CustomState] = None
        self._callbacks: Optional[MaaCustomControllerCallbacks] = None
        self._connected = False

    # ------------------------------------------------------------- 生命周期

    def connect(self) -> None:
        self._ensure_library()
        if self._config.log_dir is not None:
            self._set_log_dir(Path(self._config.log_dir))
        self._create_resource()
        self._create_controller()
        self._create_tasker()
        self._connected = True

    def close(self) -> None:
        lib = self._lib
        if lib is not None:
            if self._tasker and self._tasker.value:
                lib.MaaTaskerDestroy(self._tasker)
            if self._controller and self._controller.value:
                lib.MaaControllerDestroy(self._controller)
            if self._resource and self._resource.value:
                lib.MaaResourceDestroy(self._resource)
        self._tasker = ctypes.c_void_p()
        self._controller = ctypes.c_void_p()
        self._resource = ctypes.c_void_p()
        if self._dll_dir is not None:
            try:
                self._dll_dir.close()
            except Exception:  # pragma: no cover - 解释器退出期
                pass
            self._dll_dir = None
        self._connected = False

    def __enter__(self) -> "CtypesMaaClient":
        self.connect()
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    @property
    def custom_calls(self) -> Tuple[Tuple[Any, ...], ...]:
        return tuple(self._custom_state.calls) if self._custom_state else ()

    @property
    def config(self) -> CtypesMaaConfig:
        return self._config

    # ------------------------------------------------------------- 协议实现

    def screencap(self) -> Screenshot:
        self._require_connected()
        lib = self._lib
        cap_id = lib.MaaControllerPostScreencap(self._controller)
        if not cap_id:
            raise MaaClientError("MaaControllerPostScreencap 被拒绝")
        status = lib.MaaControllerWait(self._controller, cap_id)
        if status != STATUS_SUCCEEDED:
            raise MaaClientError(f"截图失败，Maa 状态码 {status}")
        image = ctypes.c_void_p(lib.MaaImageBufferCreate())
        try:
            if not lib.MaaControllerCachedImage(self._controller, image):
                raise MaaClientError("MaaControllerCachedImage 失败")
            width = int(lib.MaaImageBufferWidth(image))
            height = int(lib.MaaImageBufferHeight(image))
            channels = int(lib.MaaImageBufferChannels(image))
            data = self._image_bytes(image)
            return Screenshot(
                data=data,
                width=width,
                height=height,
                channels=channels,
                captured_at=self._now(),
                source=self._config.controller,
            )
        finally:
            lib.MaaImageBufferDestroy(image)

    def click(self, x: int, y: int) -> bool:
        return self._post(lib_name="MaaControllerPostClick", args=(int(x), int(y)))

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 300) -> bool:
        return self._post(
            lib_name="MaaControllerPostSwipe",
            args=(int(x1), int(y1), int(x2), int(y2), int(duration_ms)),
        )

    def click_key(self, keycode: int) -> bool:
        return self._post(lib_name="MaaControllerPostClickKey", args=(int(keycode),))

    def start_app(self, package: str) -> bool:
        return self._post(lib_name="MaaControllerPostStartApp", args=(package.encode("utf-8"),))

    def stop_app(self, package: str) -> bool:
        return self._post(lib_name="MaaControllerPostStopApp", args=(package.encode("utf-8"),))

    def recognize(
        self, reco_type: str, params: Mapping[str, Any], screenshot: Screenshot
    ) -> RecoResult:
        self._require_connected()
        if not self._resource.value or not self._tasker.value:
            raise MaaClientError("识别需要 resource 与 tasker；请检查 resource_dir")
        lib = self._lib
        image = ctypes.c_void_p(lib.MaaImageBufferCreate())
        try:
            if not self._set_encoded(image, screenshot.data):
                raise MaaClientError("把截图写入 MaaImageBuffer 失败")
            param_text = json.dumps(dict(params), ensure_ascii=False).encode("utf-8")
            task_id = lib.MaaTaskerPostRecognition(
                self._tasker, reco_type.encode("utf-8"), param_text, image
            )
            if not task_id:
                return RecoResult.miss(reco_type, "MaaTaskerPostRecognition 被拒绝")
            status = lib.MaaTaskerWait(self._tasker, task_id)
            if status != STATUS_SUCCEEDED:
                return RecoResult.miss(reco_type, f"Maa 状态码 {status}")
            detail = self._recognition_detail(task_id)
            if detail is None:
                return RecoResult.miss(reco_type, "无法取回识别详情")
            hit, box, payload = detail
            text, score = self._text_and_score(reco_type, payload)
            return RecoResult(
                reco_type=reco_type,
                hit=hit,
                box=box if hit else None,
                detail=payload,
                text=text,
                score=score,
            )
        finally:
            lib.MaaImageBufferDestroy(image)

    # ------------------------------------------------------------- 内部

    def _ensure_library(self) -> None:
        if self._lib is not None:
            return
        runtime = Path(self._config.runtime_dir)
        dll = runtime / "MaaFramework.dll"
        if not dll.is_file():
            raise MaaClientError(
                f"未找到 MaaFramework.dll: {dll}；请检查 machine.maa_runtime_dir"
            )
        try:
            self._dll_dir = os.add_dll_directory(str(runtime))
            self._lib = ctypes.CDLL(str(dll))
        except OSError as exc:
            raise MaaClientError(f"加载 MaaFramework.dll 失败: {exc}") from exc
        self._configure_api()

    def _configure_api(self) -> None:
        lib = self._lib
        lib.MaaGlobalSetOption.argtypes = [ctypes.c_int32, ctypes.c_void_p, ctypes.c_uint64]
        lib.MaaGlobalSetOption.restype = MaaBool
        lib.MaaResourceCreate.restype = ctypes.c_void_p
        lib.MaaResourcePostBundle.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
        lib.MaaResourcePostBundle.restype = ctypes.c_int64
        lib.MaaResourceWait.argtypes = [ctypes.c_void_p, ctypes.c_int64]
        lib.MaaResourceWait.restype = ctypes.c_int32
        lib.MaaResourceDestroy.argtypes = [ctypes.c_void_p]
        lib.MaaAdbControllerCreate.argtypes = [
            ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint64, ctypes.c_uint64,
            ctypes.c_char_p, ctypes.c_char_p,
        ]
        lib.MaaAdbControllerCreate.restype = ctypes.c_void_p
        lib.MaaCustomControllerCreate.argtypes = [
            ctypes.POINTER(MaaCustomControllerCallbacks), ctypes.c_void_p
        ]
        lib.MaaCustomControllerCreate.restype = ctypes.c_void_p
        lib.MaaControllerSetOption.argtypes = [
            ctypes.c_void_p, ctypes.c_int32, ctypes.c_void_p, ctypes.c_uint64
        ]
        lib.MaaControllerSetOption.restype = MaaBool
        lib.MaaControllerPostConnection.argtypes = [ctypes.c_void_p]
        lib.MaaControllerPostConnection.restype = ctypes.c_int64
        lib.MaaControllerWait.argtypes = [ctypes.c_void_p, ctypes.c_int64]
        lib.MaaControllerWait.restype = ctypes.c_int32
        lib.MaaControllerDestroy.argtypes = [ctypes.c_void_p]
        lib.MaaControllerPostScreencap.argtypes = [ctypes.c_void_p]
        lib.MaaControllerPostScreencap.restype = ctypes.c_int64
        lib.MaaControllerCachedImage.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        lib.MaaControllerCachedImage.restype = MaaBool
        lib.MaaControllerPostClick.argtypes = [ctypes.c_void_p, ctypes.c_int32, ctypes.c_int32]
        lib.MaaControllerPostClick.restype = ctypes.c_int64
        lib.MaaControllerPostSwipe.argtypes = [
            ctypes.c_void_p, ctypes.c_int32, ctypes.c_int32, ctypes.c_int32, ctypes.c_int32, ctypes.c_int32
        ]
        lib.MaaControllerPostSwipe.restype = ctypes.c_int64
        lib.MaaControllerPostClickKey.argtypes = [ctypes.c_void_p, ctypes.c_int32]
        lib.MaaControllerPostClickKey.restype = ctypes.c_int64
        lib.MaaControllerPostStartApp.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
        lib.MaaControllerPostStartApp.restype = ctypes.c_int64
        lib.MaaControllerPostStopApp.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
        lib.MaaControllerPostStopApp.restype = ctypes.c_int64
        lib.MaaTaskerCreate.restype = ctypes.c_void_p
        lib.MaaTaskerBindResource.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        lib.MaaTaskerBindResource.restype = MaaBool
        lib.MaaTaskerBindController.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        lib.MaaTaskerBindController.restype = MaaBool
        lib.MaaTaskerPostRecognition.argtypes = [
            ctypes.c_void_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_void_p
        ]
        lib.MaaTaskerPostRecognition.restype = ctypes.c_int64
        lib.MaaTaskerWait.argtypes = [ctypes.c_void_p, ctypes.c_int64]
        lib.MaaTaskerWait.restype = ctypes.c_int32
        lib.MaaTaskerDestroy.argtypes = [ctypes.c_void_p]
        lib.MaaTaskerGetTaskDetail.argtypes = [
            ctypes.c_void_p, ctypes.c_int64, ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_int64), ctypes.POINTER(ctypes.c_uint64),
            ctypes.POINTER(ctypes.c_int32),
        ]
        lib.MaaTaskerGetTaskDetail.restype = MaaBool
        lib.MaaTaskerGetNodeDetail.argtypes = [
            ctypes.c_void_p, ctypes.c_int64, ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_int64), ctypes.POINTER(ctypes.c_int64),
            ctypes.POINTER(MaaBool),
        ]
        lib.MaaTaskerGetNodeDetail.restype = MaaBool
        lib.MaaTaskerGetRecognitionDetail.argtypes = [
            ctypes.c_void_p, ctypes.c_int64, ctypes.c_void_p, ctypes.c_void_p,
            ctypes.POINTER(MaaBool), ctypes.c_void_p, ctypes.c_void_p,
            ctypes.c_void_p, ctypes.c_void_p,
        ]
        lib.MaaTaskerGetRecognitionDetail.restype = MaaBool
        lib.MaaStringBufferCreate.restype = ctypes.c_void_p
        lib.MaaStringBufferDestroy.argtypes = [ctypes.c_void_p]
        lib.MaaStringBufferGet.argtypes = [ctypes.c_void_p]
        lib.MaaStringBufferGet.restype = ctypes.c_char_p
        lib.MaaStringBufferSet.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
        lib.MaaStringBufferSet.restype = MaaBool
        lib.MaaImageBufferCreate.restype = ctypes.c_void_p
        lib.MaaImageBufferDestroy.argtypes = [ctypes.c_void_p]
        lib.MaaImageBufferSetEncoded.argtypes = [
            ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint8), ctypes.c_uint64
        ]
        lib.MaaImageBufferSetEncoded.restype = MaaBool
        lib.MaaImageBufferGetEncoded.argtypes = [ctypes.c_void_p]
        lib.MaaImageBufferGetEncoded.restype = ctypes.POINTER(ctypes.c_uint8)
        lib.MaaImageBufferGetEncodedSize.argtypes = [ctypes.c_void_p]
        lib.MaaImageBufferGetEncodedSize.restype = ctypes.c_uint64
        lib.MaaImageBufferGetRawData.argtypes = [ctypes.c_void_p]
        lib.MaaImageBufferGetRawData.restype = ctypes.c_void_p
        for name in ("MaaImageBufferWidth", "MaaImageBufferHeight", "MaaImageBufferChannels"):
            fn = getattr(lib, name)
            fn.argtypes = [ctypes.c_void_p]
            fn.restype = ctypes.c_int32
        lib.MaaRectCreate.restype = ctypes.c_void_p
        lib.MaaRectDestroy.argtypes = [ctypes.c_void_p]
        for name in ("MaaRectGetX", "MaaRectGetY", "MaaRectGetW", "MaaRectGetH"):
            fn = getattr(lib, name)
            fn.argtypes = [ctypes.c_void_p]
            fn.restype = ctypes.c_int32

    def _set_log_dir(self, log_dir: Path) -> None:
        log_dir.mkdir(parents=True, exist_ok=True)
        raw = os.fsencode(os.fspath(log_dir))
        buffer = ctypes.create_string_buffer(raw)
        self._lib.MaaGlobalSetOption(
            OPTION_LOG_DIR, ctypes.cast(buffer, ctypes.c_void_p), len(raw)
        )

    def _create_resource(self) -> None:
        lib = self._lib
        if self._config.resource_dir is None:
            return
        resource_dir = Path(self._config.resource_dir)
        if not resource_dir.is_dir():
            raise MaaClientError(
                f"资源目录不存在: {resource_dir}；请检查 machine.maa_resource_dir"
            )
        self._resource = ctypes.c_void_p(lib.MaaResourceCreate())
        if not self._resource.value:
            raise MaaClientError("MaaResourceCreate 失败")
        res_id = lib.MaaResourcePostBundle(
            self._resource, os.fsencode(os.fspath(resource_dir))
        )
        status = lib.MaaResourceWait(self._resource, res_id)
        if status != STATUS_SUCCEEDED:
            raise MaaClientError(f"Maa 资源加载失败，状态码 {status}（{resource_dir}）")

    def _create_controller(self) -> None:
        lib = self._lib
        if self._config.controller == "adb":
            # 先做 ADB 预检，避免模拟器刚启动/offline 时 MAA 内部 adb 子进程
            # 反复报 `settings get secure android_id` child return error。
            from .adb import ensure_maa_ready

            ensure_maa_ready(
                str(self._config.adb_path),
                str(self._config.adb_address),
                package_name=self._config.package_name,
                timeout=45.0,
            )
            agent = self._config.agent_dir or (
                self._config.runtime_dir / "MaaAgentBinary"
            )
            last_status: Optional[int] = None
            for attempt in range(3):
                self._controller = ctypes.c_void_p(
                    lib.MaaAdbControllerCreate(
                        os.fsencode(os.fspath(self._config.adb_path)),
                        self._config.adb_address.encode("utf-8"),
                        self._config.screencap_methods,
                        self._config.input_methods,
                        b"{}",
                        os.fsencode(os.fspath(agent)),
                    )
                )
                if not self._controller.value:
                    raise MaaClientError("MaaControllerCreate 失败")
                if self._config.short_side:
                    short_side = ctypes.c_int32(int(self._config.short_side))
                    lib.MaaControllerSetOption(
                        self._controller,
                        OPTION_SCREENSHOT_SHORT_SIDE,
                        ctypes.byref(short_side),
                        ctypes.sizeof(short_side),
                    )
                conn_id = lib.MaaControllerPostConnection(self._controller)
                status = lib.MaaControllerWait(self._controller, conn_id)
                if status == STATUS_SUCCEEDED:
                    return
                last_status = status
                if self._controller.value:
                    lib.MaaControllerDestroy(self._controller)
                    self._controller = ctypes.c_void_p()
                if attempt < 2:
                    time.sleep(2.0)
            raise MaaClientError(
                f"Maa 控制器连接失败，状态码 {last_status}（已重试 3 次）"
            )
        self._controller = self._create_custom_controller()
        if not self._controller.value:
            raise MaaClientError("MaaControllerCreate 失败")

    def _create_custom_controller(self) -> Any:
        lib = self._lib
        images = list(self._config.custom_images)
        if not images and self._config.custom_dir is not None:
            directory = Path(self._config.custom_dir)
            if not directory.is_dir():
                raise MaaClientError(f"自定义控制器截图目录不存在: {directory}")
            images = [p.read_bytes() for p in sorted(directory.glob("*.png"))]
        if not images:
            raise MaaClientError("自定义控制器没有可用截图")
        state = _CustomState(images)
        key = _register_state(state)
        self._custom_state = state
        callbacks = self._build_callbacks(state)
        self._callbacks = callbacks
        return ctypes.c_void_p(
            lib.MaaCustomControllerCreate(ctypes.byref(callbacks), ctypes.c_void_p(key))
        )

    def _build_callbacks(self, state: _CustomState) -> MaaCustomControllerCallbacks:
        lib = self._lib

        def connect(_arg: Any) -> int:
            state.connected = True
            state.calls.append(("connect",))
            return 1

        def connected(_arg: Any) -> int:
            return 1 if state.connected else 0

        def request_uuid(_arg: Any, buffer: Any) -> int:
            lib.MaaStringBufferSet(buffer, b"qqreader-custom")
            return 1

        def get_features(_arg: Any) -> int:
            return 0

        def start_app(intent: Any, arg: Any) -> int:
            current = _lookup_state(arg)
            if current is not None:
                current.calls.append(("start_app", intent.decode("utf-8") if intent else ""))
            return 1

        def stop_app(intent: Any, arg: Any) -> int:
            current = _lookup_state(arg)
            if current is not None:
                current.calls.append(("stop_app", intent.decode("utf-8") if intent else ""))
            return 1

        def screencap(_arg: Any, buffer: Any) -> int:
            current = _lookup_state(_arg)
            if current is None:
                return 0
            data = current.next_image()
            array = (ctypes.c_uint8 * len(data)).from_buffer_copy(data)
            return 1 if lib.MaaImageBufferSetEncoded(buffer, array, len(data)) else 0

        def click(x: int, y: int, arg: Any) -> int:
            current = _lookup_state(arg)
            if current is not None:
                current.calls.append(("click", x, y))
            return 1

        def swipe(x1: int, y1: int, x2: int, y2: int, duration: int, arg: Any) -> int:
            current = _lookup_state(arg)
            if current is not None:
                current.calls.append(("swipe", x1, y1, x2, y2, duration))
            return 1

        def click_key(keycode: int, arg: Any) -> int:
            current = _lookup_state(arg)
            if current is not None:
                current.calls.append(("click_key", keycode))
            return 1

        def input_text(text: Any, arg: Any) -> int:
            current = _lookup_state(arg)
            if current is not None:
                current.calls.append(("input_text", text.decode("utf-8") if text else ""))
            return 1

        def noop_bool(*_args: Any) -> int:
            return 1

        def noop_shell(*_args: Any) -> int:
            return 0

        keep = [
            _CONNECT(connect),
            _CONNECTED(connected),
            _REQUEST_UUID(request_uuid),
            _GET_FEATURES(get_features),
            _START_APP(start_app),
            _STOP_APP(stop_app),
            _SCREENCAP(screencap),
            _CLICK(click),
            _SWIPE(swipe),
            _TOUCH_DOWN(noop_bool),
            _TOUCH_MOVE(noop_bool),
            _TOUCH_UP(noop_bool),
            _CLICK_KEY(click_key),
            _INPUT_TEXT(input_text),
            _KEY_EVENT(noop_bool),
            _KEY_EVENT(noop_bool),
            _SCROLL(noop_bool),
            _RELATIVE_MOVE(noop_bool),
            _SHELL(noop_shell),
            _INACTIVE(noop_bool),
            _GET_INFO(noop_shell),
        ]
        state.keep_alive.extend(keep)
        return MaaCustomControllerCallbacks(*keep)

    def _create_tasker(self) -> None:
        lib = self._lib
        self._tasker = ctypes.c_void_p(lib.MaaTaskerCreate())
        if not self._tasker.value:
            raise MaaClientError("MaaTaskerCreate 失败")
        if self._resource.value and not lib.MaaTaskerBindResource(self._tasker, self._resource):
            raise MaaClientError("MaaTaskerBindResource 失败")
        if not lib.MaaTaskerBindController(self._tasker, self._controller):
            raise MaaClientError("MaaTaskerBindController 失败")

    def _post(self, *, lib_name: str, args: Tuple[Any, ...]) -> bool:
        self._require_connected()
        lib = self._lib
        post = getattr(lib, lib_name)
        request_id = post(self._controller, *args)
        if not request_id:
            return False
        return lib.MaaControllerWait(self._controller, request_id) == STATUS_SUCCEEDED

    def _recognition_detail(
        self, task_id: int
    ) -> Optional[Tuple[bool, Optional[Box], Dict[str, Any]]]:
        lib = self._lib
        entry = ctypes.c_void_p(lib.MaaStringBufferCreate())
        node_ids = (ctypes.c_int64 * 16)()
        node_size = ctypes.c_uint64(16)
        task_status = ctypes.c_int32(0)
        try:
            if not lib.MaaTaskerGetTaskDetail(
                self._tasker, task_id, entry, node_ids,
                ctypes.byref(node_size), ctypes.byref(task_status),
            ):
                return None
            reco_id = 0
            for index in range(min(node_size.value, 16)):
                node_name = ctypes.c_void_p(lib.MaaStringBufferCreate())
                reco = ctypes.c_int64(0)
                action = ctypes.c_int64(0)
                completed = MaaBool(0)
                try:
                    if lib.MaaTaskerGetNodeDetail(
                        self._tasker, node_ids[index], node_name,
                        ctypes.byref(reco), ctypes.byref(action), ctypes.byref(completed),
                    ) and reco.value:
                        reco_id = reco.value
                        break
                finally:
                    lib.MaaStringBufferDestroy(node_name)
            if not reco_id:
                return None
            node_name = ctypes.c_void_p(lib.MaaStringBufferCreate())
            algorithm = ctypes.c_void_p(lib.MaaStringBufferCreate())
            detail_buffer = ctypes.c_void_p(lib.MaaStringBufferCreate())
            hit = MaaBool(0)
            box = ctypes.c_void_p(lib.MaaRectCreate())
            try:
                if not lib.MaaTaskerGetRecognitionDetail(
                    self._tasker, reco_id, node_name, algorithm,
                    ctypes.byref(hit), box, detail_buffer, None, None,
                ):
                    return None
                box_value = (
                    int(lib.MaaRectGetX(box)),
                    int(lib.MaaRectGetY(box)),
                    int(lib.MaaRectGetW(box)),
                    int(lib.MaaRectGetH(box)),
                )
                raw = lib.MaaStringBufferGet(detail_buffer) or b""
                payload = json.loads(raw.decode("utf-8")) if raw else {}
                return bool(hit.value), box_value, payload
            finally:
                lib.MaaRectDestroy(box)
                lib.MaaStringBufferDestroy(detail_buffer)
                lib.MaaStringBufferDestroy(algorithm)
                lib.MaaStringBufferDestroy(node_name)
        finally:
            lib.MaaStringBufferDestroy(entry)

    def _image_bytes(self, image: Any) -> bytes:
        lib = self._lib
        size = int(lib.MaaImageBufferGetEncodedSize(image))
        pointer = lib.MaaImageBufferGetEncoded(image)
        if size > 0 and pointer:
            return ctypes.string_at(pointer, size)
        width = int(lib.MaaImageBufferWidth(image))
        height = int(lib.MaaImageBufferHeight(image))
        channels = int(lib.MaaImageBufferChannels(image))
        raw = lib.MaaImageBufferGetRawData(image)
        if not raw or width <= 0 or height <= 0 or channels <= 0:
            raise MaaClientError("截图缓冲区为空")
        try:
            import cv2  # type: ignore[import-not-found]
            import numpy as np  # type: ignore[import-not-found]

            frame = np.frombuffer(
                ctypes.string_at(raw, width * height * channels), dtype=np.uint8
            ).reshape(height, width, channels)
            ok, encoded = cv2.imencode(".png", frame)
            if not ok:
                raise MaaClientError("原始截图编码 PNG 失败")
            return encoded.tobytes()
        except ImportError as exc:  # pragma: no cover - 取决于环境
            raise MaaClientError(
                "截图没有编码数据，且未安装 numpy/opencv 无法转换"
            ) from exc

    def _set_encoded(self, image: Any, data: bytes) -> bool:
        if not data:
            return False
        array = (ctypes.c_uint8 * len(data)).from_buffer_copy(data)
        return bool(self._lib.MaaImageBufferSetEncoded(image, array, len(data)))

    def _require_connected(self) -> None:
        if not self._connected or self._lib is None or not self._controller.value:
            raise MaaClientError("Maa 客户端尚未 connect()")

    def _now(self) -> float:
        if self._clock is not None:
            return float(self._clock.now())
        return time.time()

    @staticmethod
    def _text_and_score(
        reco_type: str, payload: Mapping[str, Any]
    ) -> Tuple[Optional[str], Optional[float]]:
        best = payload.get("best") if isinstance(payload, Mapping) else None
        if isinstance(best, Mapping):
            text = best.get("text")
            score = best.get("score")
            return (str(text) if text else None, float(score) if score is not None else None)
        all_items = payload.get("all") if isinstance(payload, Mapping) else None
        if isinstance(all_items, Sequence) and all_items:
            first = all_items[0]
            if isinstance(first, Mapping):
                text = first.get("text")
                score = first.get("score")
                return (str(text) if text else None, float(score) if score is not None else None)
        return None, None
