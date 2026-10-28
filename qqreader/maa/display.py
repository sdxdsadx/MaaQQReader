"""设备分辨率兼容检查。

任务坐标和 ROI 都写在 MaaFramework 的「短边 720」缩放空间里（截图被缩放到
720 宽，点击再按比例映射回设备像素），参考画面是 720×1280、240 DPI（480dp 宽，
2026-10-28 读自日常使用的 MuMu 12 实例 0：``wm size`` 720x1280、``wm density`` 240）。
所以：

* 竖屏、9:16 的任意分辨率（720×1280、1080×1920、1440×2560）缩放后都是 720×1280，
  坐标可直接复用；
* 比例不是 9:16（例如 1080×2400）时缩放后长边不是 1280，按 y 写死的 ROI 会错位；
* 横屏时 QQ 阅读的竖屏页面被旋转或加黑边，整套坐标都不成立；
* DPI 与宽度不匹配（例如 720×1280 配 320 DPI、1080×1920 配 240 DPI）时 App 的版式变了，
  字号和按钮位置都不同于参考画面。

本模块只读设备参数、给出结论，不修改设备设置。
"""

from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass
from typing import Optional, Tuple

#: 参考画面（所有 pipeline 坐标都按它标定）。
REFERENCE_SIZE: Tuple[int, int] = (720, 1280)
REFERENCE_DENSITY = 240
#: 参考画面的逻辑宽度（dp）= 720 * 160 / 240。
REFERENCE_DP_WIDTH = REFERENCE_SIZE[0] * 160 / REFERENCE_DENSITY
#: 缩放到短边 720 后长边允许的误差（像素）。
LONG_SIDE_TOLERANCE = 8
#: 逻辑宽度允许的相对误差。
DP_TOLERANCE = 0.05

LEVEL_OK = "ok"
LEVEL_WARN = "warn"
LEVEL_FAIL = "fail"
LEVEL_UNKNOWN = "unknown"

_SIZE_RE = re.compile(r"(Physical|Override) size:\s*(\d+)\s*x\s*(\d+)", re.IGNORECASE)
_DENSITY_RE = re.compile(r"(Physical|Override) density:\s*(\d+)", re.IGNORECASE)


@dataclass(frozen=True)
class DisplayInfo:
    """设备当前生效的分辨率与 DPI（有 Override 时取 Override）。"""

    width: int
    height: int
    density: Optional[int] = None

    @property
    def dp_width(self) -> Optional[float]:
        if not self.density:
            return None
        return min(self.width, self.height) * 160 / self.density

    def describe(self) -> str:
        dpi = f" @ {self.density} DPI" if self.density else ""
        return f"{self.width}×{self.height}{dpi}"


@dataclass(frozen=True)
class DisplayAssessment:
    level: str
    info: Optional[DisplayInfo]
    reasons: Tuple[str, ...] = ()
    suggestion: str = ""

    @property
    def ok(self) -> bool:
        """``fail`` 才算不可用；``warn`` / ``unknown`` 仍可运行。"""
        return self.level != LEVEL_FAIL

    def render(self) -> str:
        head = self.info.describe() if self.info else "分辨率未知"
        parts = [f"[{self.level}] {head}"]
        parts.extend(self.reasons)
        if self.suggestion:
            parts.append(self.suggestion)
        return "；".join(parts)


def parse_wm_size(text: str) -> Optional[Tuple[int, int]]:
    """解析 ``adb shell wm size``；有 Override 时以 Override 为准。"""
    found = {}
    for kind, width, height in _SIZE_RE.findall(text or ""):
        found[kind.lower()] = (int(width), int(height))
    return found.get("override") or found.get("physical")


def parse_wm_density(text: str) -> Optional[int]:
    """解析 ``adb shell wm density``；有 Override 时以 Override 为准。"""
    found = {}
    for kind, value in _DENSITY_RE.findall(text or ""):
        found[kind.lower()] = int(value)
    return found.get("override") or found.get("physical")


def scaled_size(width: int, height: int, short_side: int = REFERENCE_SIZE[0]) -> Tuple[int, int]:
    """按 MaaFramework 的规则把截图缩放到指定短边，返回缩放后的 (宽, 高)。"""
    if width <= 0 or height <= 0:
        raise ValueError(f"分辨率必须为正数: {width}x{height}")
    if width <= height:
        return short_side, int(round(height * short_side / width))
    return int(round(width * short_side / height)), short_side


def device_scale(info: Optional[DisplayInfo]) -> float:
    """设备短边 / 720：把 720×1280 坐标换成设备像素时乘它（读不到分辨率按 1）。

    只给绕过 Maa 直接 ``adb shell input`` 的代码用；经 Maa 的点击已由 Maa 换算。
    """
    if info is None:
        return 1.0
    return min(info.width, info.height) / REFERENCE_SIZE[0]


def recommended_density(width: int, height: int) -> int:
    """让逻辑宽度等于参考画面（480dp）的 DPI。"""
    return int(round(min(width, height) * 160 / REFERENCE_DP_WIDTH))


def assess_display(info: Optional[DisplayInfo]) -> DisplayAssessment:
    """判断设备画面能否直接套用 720×1280 标定的坐标。"""
    if info is None:
        return DisplayAssessment(
            LEVEL_UNKNOWN, None, ("读不到 wm size，跳过分辨率检查",)
        )
    reasons = []
    level = LEVEL_OK
    suggestion = ""
    if info.width > info.height:
        return DisplayAssessment(
            LEVEL_FAIL,
            info,
            ("横屏分辨率：QQ 阅读是竖屏应用，720×1280 标定的坐标全部不成立",),
            "请在模拟器设置里改成竖屏（手机版）分辨率 720×1280 / 240 DPI",
        )
    sw, sh = scaled_size(info.width, info.height)
    if abs(sh - REFERENCE_SIZE[1]) > LONG_SIDE_TOLERANCE:
        level = LEVEL_FAIL
        reasons.append(
            f"屏幕比例不是 9:16：缩放到短边 720 后是 {sw}×{sh}，"
            f"按 720×1280 标定的纵向坐标会错位"
        )
        suggestion = "请把模拟器分辨率改成 720×1280 / 240 DPI（或 1080×1920 / 360 DPI）"
    dp = info.dp_width
    if dp is not None and abs(dp - REFERENCE_DP_WIDTH) / REFERENCE_DP_WIDTH > DP_TOLERANCE:
        level = LEVEL_FAIL
        reasons.append(
            f"DPI 与分辨率不匹配：逻辑宽度 {dp:.0f}dp（参考 {REFERENCE_DP_WIDTH:.0f}dp），"
            "App 版式与标定画面不同"
        )
        suggestion = suggestion or (
            f"请把 DPI 改成 {recommended_density(info.width, info.height)}"
        )
    if level == LEVEL_OK and (info.width, info.height) != REFERENCE_SIZE:
        level = LEVEL_WARN
        reasons.append(
            "9:16 非 720×1280：识别与点击按比例缩放可用；"
            "滑块验证码的 sendevent 拖动按 720×1280 像素写坐标，自动过滑块可能失败"
        )
        suggestion = "推荐 720×1280 / 240 DPI"
    if level == LEVEL_OK:
        reasons.append("与标定画面一致")
    return DisplayAssessment(level, info, tuple(reasons), suggestion)


def query_display(adb_path: str, address: str, *, timeout: float = 10.0) -> Optional[DisplayInfo]:
    """用 ``wm size`` / ``wm density`` 读取设备当前分辨率；读不到返回 None。"""
    from .adb import run_adb

    size_result = run_adb(adb_path, "-s", address, "shell", "wm", "size", timeout=timeout)
    if size_result is None or size_result.returncode != 0:
        return None
    size = parse_wm_size(size_result.stdout)
    if size is None:
        return None
    density_result = run_adb(adb_path, "-s", address, "shell", "wm", "density", timeout=timeout)
    density = None
    if density_result is not None and density_result.returncode == 0:
        density = parse_wm_density(density_result.stdout)
    return DisplayInfo(size[0], size[1], density)


def check_device_display(adb_path: str, address: str) -> DisplayAssessment:
    return assess_display(query_display(adb_path, address))


#: 环境变量：``strict``（默认，不兼容就拒绝连接）/ ``warn``（只提示）/ ``off``（不检查）。
DISPLAY_CHECK_ENV = "QQREADER_DISPLAY_CHECK"


def enforce_display(
    adb_path: str,
    address: str,
    *,
    mode: Optional[str] = None,
    query=None,
    stream=None,
) -> DisplayAssessment:
    """连接设备时调用：不兼容的分辨率在开跑前就报清楚，而不是跑到一半识别失败。"""
    from .client import MaaClientError

    mode = (mode or os.environ.get(DISPLAY_CHECK_ENV) or "strict").strip().lower()
    if mode == "off":
        return DisplayAssessment(LEVEL_UNKNOWN, None, ("已关闭分辨率检查",))
    info = (query or query_display)(adb_path, address)
    assessment = assess_display(info)
    out = stream if stream is not None else sys.stderr
    if assessment.level in (LEVEL_WARN, LEVEL_FAIL):
        print(f"[display] {address} 分辨率检查: {assessment.render()}", file=out, flush=True)
    if assessment.level == LEVEL_FAIL and mode == "strict":
        raise MaaClientError(
            f"设备 {address} 分辨率不兼容：{assessment.render()}"
            f"（确认要继续可设环境变量 {DISPLAY_CHECK_ENV}=warn）"
        )
    return assessment
