"""自动阅读脚本（以老版本 `_run_direct_reading` 为样本重构）。

## 为什么这样设计

老版本（备份 `gui/maa_qq_reader_gui.py:71-74`）的结论：

> QQ 阅读正文页启用 FLAG_SECURE，不能把"自动阅读"按钮是否响应作为唯一成功
> 条件。每段停留不超过 15 分钟，返回书架后重新进书，确保即使自动翻页失效
> 也能稳定累计在线阅读时长。

重构前的脚本反其道而行：扫正文页顶部 100px 找书名关键词、OCR 读
「自动阅读中」、等「已开启自动阅读」toast、用正文首行是否变化判断是否翻页。
这四件事都要回读正文页，而正文页读不出来，因此实测全部失败（2026-09-15：
白名单误判、`enable_auto_read` 两次拿不到 toast）。

本脚本按老版本重建，**不回读正文页**：

1. 总时长切成 ≤ `SEGMENT_MINUTES`（默认 15）的段，每段重新进书 —— 保证服务端
   稳定累计时长，且单段失败只损失一段。
2. 每段的动作链：启动 App → 回书架 → Maa 识别目标书并点击 →（点击后不再截图）
   等 `ReaderPageActivity` → 盲点「自动阅读」（best-effort，失败只记日志）→
   按分钟 dwell 计时 → 返回可截图页面。
3. **唯一成功判据：`ReaderPageActivity` 停留满本段时长。** 不依赖按钮响应、
   toast、翻页证据。
4. 目标书由 Maa 的模板/书名 OCR 选定，所以不再需要「事后扫顶部 OCR 白名单」
   这种校不到实处的校验 —— 选书本身就是白名单。

目标书与识别参数见下方 `TARGET_*` 常量，与 pipeline 里
`ReadingFindBook*` 节点保持一致。

用法：
    py -3.10 scripts/auto_read_30min.py --minutes 35
    py -3.10 scripts/auto_read_30min.py --minutes 35 --segment-minutes 15
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from qqreader.config import load_config

LOG = ROOT / "runtime" / "logs" / "auto_read.log"

# 老版本 DIRECT_READING_DWELL_SEGMENT_MINUTES
SEGMENT_MINUTES = 15

# 目标书识别（与 pipeline ReadingFindBook / ReadingFindBookByTitleTerminal 对齐）
TARGET_COVER_TEMPLATE = "reading_target_uchiha_cover.png"
TARGET_COVER_THRESHOLD = 0.82
TARGET_COVER_ROI = (0, 220, 720, 960)
TARGET_TITLE_PATTERN = r"宇智波.*扉间人柱力|宇智波：从扉间人柱力开始"
TARGET_TITLE_ROI = (90, 180, 620, 900)

# 进正文后盲点「自动阅读」三连（老版本 _run_direct_reading 原值，best-effort）
AUTO_READ_TAPS = ((360, 640), (450, 1214), (360, 1125))

PACKAGE = "com.qq.reader"
READER_ACTIVITY = "ReaderPageActivity"
EXIT_DIALOG_MARKERS = ("退出QQ阅读", "退出 QQ 阅读", "退出软件", "确定退出", "是否退出")
EXIT_DIALOG_CANCELS = {"取消", "暂不退出", "继续使用"}

_client = None
_adb_path = ""
_adb_address = ""


def log(msg: str) -> None:
    line = f"[{datetime.now():%H:%M:%S}] {msg}"
    print(line, flush=True)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


# --------------------------------------------------------------- adb 基础


def adb(*args: str, timeout: int = 20) -> str:
    """原始 adb 调用；返回 stdout 文本（失败返回空串）。"""
    try:
        result = subprocess.run(
            [_adb_path, "-s", _adb_address, *args],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.SubprocessError) as exc:
        log(f"adb 调用异常: {exc}")
        return ""
    if result.returncode != 0:
        return ""
    return result.stdout.decode("utf-8", errors="replace")


def tap(x: int, y: int) -> None:
    adb("shell", "input", "tap", str(x), str(y))


def press_back() -> None:
    adb("shell", "input", "keyevent", "4")


def launch_app() -> None:
    adb("shell", "monkey", "-p", PACKAGE, "-c",
        "android.intent.category.LAUNCHER", "1", timeout=30)


def capture_available() -> bool:
    """ADB 当前能否截到 PNG（正文页 FLAG_SECURE 时为否）。"""
    try:
        result = subprocess.run(
            [_adb_path, "-s", _adb_address, "exec-out", "screencap", "-p"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=15,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.SubprocessError):
        return False
    data = result.stdout
    return result.returncode == 0 and len(data) > 100 and data.startswith(b"\x89PNG")


def reader_focus() -> str:
    return adb("shell", "dumpsys", "window", timeout=15)


def wait_reader_page(timeout: float = 8.0) -> bool:
    """等待进入 QQ 阅读受保护的正文页。"""
    deadline = time.monotonic() + max(0.5, timeout)
    while time.monotonic() < deadline:
        if READER_ACTIVITY in reader_focus():
            return True
        time.sleep(0.4)
    return False


def ui_dump() -> ET.Element | None:
    """uiautomator dump 一个可截图页面，用于「是不是书架」这类结构性判断。"""
    remote = "/sdcard/qqreader_autoread_window.xml"
    if not adb("shell", "uiautomator", "dump", remote, timeout=25):
        return None
    text = adb("shell", "cat", remote, timeout=20)
    if not text.strip():
        return None
    try:
        return ET.fromstring(text)
    except ET.ParseError:
        return None


def ui_label(node: ET.Element) -> str:
    return (node.attrib.get("text", "") or node.attrib.get("content-desc", "")).strip()


def ui_bounds(node: ET.Element) -> tuple[int, int, int, int] | None:
    """把 UIAutomator 的 bounds 转成 (x, y, width, height)。"""
    match = re.fullmatch(r"\[(\d+),(\d+)]\[(\d+),(\d+)]", node.attrib.get("bounds", ""))
    if not match:
        return None
    left, top, right, bottom = (int(value) for value in match.groups())
    if right <= left or bottom <= top:
        return None
    return left, top, right - left, bottom - top


def locate_allowed_book_ui() -> tuple[tuple[int, int, int, int] | None, str]:
    """用 Android UI 层级定位白名单书目，不依赖 MuMu 的截图通道。"""
    root = ui_dump()
    if root is None:
        return None, "UI 层级不可读"
    observed: list[str] = []
    for node in root.iter():
        label = ui_label(node)
        if label:
            observed.append(label.replace("\n", " "))
        if not any(keyword in label for keyword in ALLOWED_BOOK_KEYWORDS):
            continue
        bounds = ui_bounds(node)
        if bounds is not None:
            return bounds, f"UI 书名 {label!r}"
    sample = " | ".join(observed[:8]) or "未识别到书名"
    return None, f"UI 层级未识别到白名单书目：{sample!r}"


def ui_contains(expected: str) -> bool:
    root = ui_dump()
    if root is None:
        return False
    return expected in " ".join(ui_label(n) for n in root.iter())


def dismiss_exit_dialog() -> bool:
    """QQ 阅读按返回键偶尔弹「退出QQ阅读」，点取消。"""
    root = ui_dump()
    if root is None:
        return False
    all_text = " ".join(ui_label(n) for n in root.iter())
    if not any(marker in all_text for marker in EXIT_DIALOG_MARKERS):
        return False
    for node in root.iter():
        if ui_label(node) not in EXIT_DIALOG_CANCELS:
            continue
        match = re.fullmatch(r"\[(\d+),(\d+)]\[(\d+),(\d+)]", node.attrib.get("bounds", ""))
        if not match:
            continue
        left, top, right, bottom = (int(v) for v in match.groups())
        tap((left + right) // 2, (top + bottom) // 2)
        log(f"检测到退出确认弹窗，已点「{ui_label(node)}」")
        return True
    return False


def return_to_capturable(max_backs: int = 6) -> None:
    """离开 FLAG_SECURE 正文页，回到 Maa 能截图的页面。"""
    if capture_available():
        return
    for attempt in range(1, max_backs + 1):
        press_back()
        time.sleep(1.5)
        if dismiss_exit_dialog():
            time.sleep(1.0)
            continue
        if capture_available():
            log(f"已返回可截图页面（返回 {attempt} 次）")
            return
    raise RuntimeError("多次返回后 QQ 阅读仍禁止截图")


def return_to_shelf(max_backs: int = 4) -> None:
    """确保停在书架页（而不是同样可截图的奖励页）。"""
    return_to_capturable(max_backs=max_backs + 2)
    for attempt in range(0, max_backs + 1):
        if ui_contains("书架"):
            if attempt:
                log(f"已返回书架（额外返回 {attempt} 次）")
            return
        if attempt >= max_backs:
            break
        press_back()
        time.sleep(1.2)
        dismiss_exit_dialog()
    raise RuntimeError("未能回到 QQ 阅读书架")


# ------------------------------------------------------------- 选书与计时


class BookNotAllowed(RuntimeError):
    """书架上找不到白名单书目 —— 不静默继续，由 main 以 exit(3) 退出。"""


ALLOWED_BOOK_KEYWORDS = ("宇智波",)


def _locate_allowed_book(client) -> tuple[tuple[int, int, int, int] | None, str]:
    """在书架上定位白名单书目，返回 (box 或 None, 说明)。

    判定依据是 **Maa 对书架的识别结果**（封面模板 / 书名 OCR），不是正文页
    顶部 OCR —— 正文页顶部只显示章标题，用它判定会误拒正确书目
    （2026-09-15 实测：同一本《宇智波：从扉间人柱力开始》，章首能过、
    正文中段被误判为"不在白名单"）。封面模板本身就是白名单书目，命中即可。
    """
    shot = client.screencap()
    template = client.recognize(
        "TemplateMatch",
        {
            "template": TARGET_COVER_TEMPLATE,
            "threshold": TARGET_COVER_THRESHOLD,
            "roi": list(TARGET_COVER_ROI),
        },
        shot,
    )
    if template.hit and template.box:
        return template.box, f"封面模板 score={template.score:.3f}"

    ocr = client.recognize(
        "OCR",
        {"expected": TARGET_TITLE_PATTERN, "roi": list(TARGET_TITLE_ROI)},
        shot,
    )
    text = ocr.text or ""
    if ocr.hit and ocr.box and any(kw in text for kw in ALLOWED_BOOK_KEYWORDS):
        return ocr.box, f"书名 OCR {text!r}"

    observed = text or "未识别到书名"
    return None, f"书架未识别到白名单书目（允许：{'/'.join(ALLOWED_BOOK_KEYWORDS)}）：{observed!r}"


def _verify_book_allowed(client) -> tuple[bool, str]:
    """书源校验：书架上的目标书是否属于自动阅读白名单。"""
    box, message = _locate_allowed_book(client)
    if box is None:
        return False, f"当前书不在自动阅读白名单: {message}"
    return True, message


def click_target_book(max_attempts: int = 3) -> None:
    """在书架上确认白名单书目并点击；点击后不再截图。

    判定与点击用的是同一份 Maa 识别结果（模板优先，退到书名 OCR），所以
    **不可能**点到白名单以外的书 —— 选书本身就是守门。多次仍识别不到
    白名单书目时抛 `BookNotAllowed`，由 main 以 exit(3) 退出、不静默继续。
    """
    last = ""
    for attempt in range(1, max_attempts + 1):
        hit_box, message = locate_allowed_book_ui()
        if hit_box is None:
            last = message
            log(f"第 {attempt}/{max_attempts} 次：{message}，按返回键后重试")
            press_back()
            time.sleep(2.0)
            continue

        x, y, w, h = hit_box
        tap(x + w // 2, y + h // 2)
        log(f"已点击白名单书目（{message}）box=({x},{y},{w},{h})")
        if wait_reader_page(8.0):
            return
        # 未直接进正文：老版本按 (500,1126) 点「查看原文」备用入口
        tap(500, 1126)
        log("未直接进入正文页，已点「查看原文」备用入口")
        if wait_reader_page(8.0):
            return
        log(f"第 {attempt}/{max_attempts} 次点击后仍未进入正文页")
        last = "点击后未进入正文页"
    raise BookNotAllowed(f"{last}（{max_attempts} 次尝试均失败）")


def best_effort_auto_read() -> None:
    """盲点「自动阅读」。正文页读不回状态，所以只尝试、不校验。"""
    try:
        for x, y in AUTO_READ_TAPS:
            tap(x, y)
            time.sleep(1.0)
        log("已尝试点击「自动阅读」；本段仍以正文停留计时为准")
    except Exception as exc:  # noqa: BLE001 - 盲点失败不影响 dwell 计时
        log(f"自动阅读按钮操作未确认，继续使用正文停留保底：{exc}")


def dwell(minutes: int, segment: int, segments: int) -> None:
    """在正文页主动翻页并计时。

    仅停留在 ReaderPageActivity 不保证服务端累计阅读时长；MuMu 上自动阅读开关
    又可能因重复点击而反向关闭。因此每 18 秒补一次纵向翻页，分钟心跳同时确认
    正文 Activity 仍在前台。
    """
    for minute in range(1, minutes + 1):
        for _ in range(3):
            # 用户已将阅读器设为上下滚动模式；纵向上滑避开正文评论热点。
            adb("shell", "input", "swipe", "360", "1050", "360", "350", "500")
            time.sleep(18)
        if READER_ACTIVITY not in reader_focus():
            raise RuntimeError(f"第 {segment}/{segments} 段第 {minute} 分钟时已离开正文页")
        # 三次翻页耗时约 54 秒，补足一分钟后再记心跳。
        time.sleep(6)
        log(
            f"正文主动翻页 第 {segment}/{segments} 段：{minute}/{minutes} 分钟"
            f"（本段剩 {minutes - minute} 分钟）"
        )


def segments_for(minutes: int, segment_minutes: int) -> list[int]:
    """把总时长切成每段不超过 segment_minutes 的时长列表。"""
    if segment_minutes < 1:
        raise ValueError("segment_minutes 必须 >= 1")
    out: list[int] = []
    remaining = minutes
    while remaining > 0:
        take = min(segment_minutes, remaining)
        out.append(take)
        remaining -= take
    return out or [0]


def main() -> int:
    global _client, _adb_path, _adb_address
    parser = argparse.ArgumentParser(description="QQ 阅读自动阅读（dwell 计时）")
    parser.add_argument("--minutes", type=int, default=30, help="总阅读时长（分钟）")
    parser.add_argument("--segment-minutes", type=int, default=SEGMENT_MINUTES,
                        help="单段停留上限，默认 15（老版本值）")
    args = parser.parse_args()
    if args.minutes < 1:
        log("--minutes 必须 >= 1")
        return 2

    config = load_config("configs/qqreader.local.json")
    _adb_path = config.machine.adb_path
    _adb_address = config.machine.adb_address
    # MuMu 12 偶发在 Maa 截图测速后让 screencap 持续返回空 PNG。
    # 选书改用 UIAutomator 层级，正文仍只以 ReaderPageActivity 停留计时。
    _client = None

    plan = segments_for(args.minutes, args.segment_minutes)
    log(f"=== 自动阅读 {args.minutes} 分钟开始（{len(plan)} 段：{plan}）===")

    try:
        return_to_capturable()
        for index, dwell_minutes in enumerate(plan, start=1):
            log(f"--- 第 {index}/{len(plan)} 段：{dwell_minutes} 分钟 ---")
            launch_app()
            time.sleep(3.0)
            return_to_shelf()
            hit_box, why = locate_allowed_book_ui()
            if hit_box is None:
                log(f"当前书不在自动阅读白名单: {why}")
                log("书源校验未通过 → 不进入自动阅读（exit 3）")
                return 3
            log(f"书源校验通过：{why}")
            click_target_book()
            best_effort_auto_read()
            dwell(dwell_minutes, index, len(plan))
            return_to_capturable()
            log(f"第 {index}/{len(plan)} 段完成，已返回可截图页面")
    except KeyboardInterrupt:
        log("用户中断，尝试返回可截图页面")
        try:
            return_to_capturable()
        except RuntimeError as exc:
            log(f"中断清理失败：{exc}")
        return 130
    except BookNotAllowed as exc:
        log(f"❌ 书源校验/选书失败：{exc}")
        try:
            return_to_capturable()
        except RuntimeError:
            pass
        return 3
    except RuntimeError as exc:
        log(f"❌ 自动阅读失败：{exc}")
        try:
            return_to_capturable()
        except RuntimeError:
            pass
        return 2
    finally:
        if _client is not None:
            _client.close()

    log(f"=== 自动阅读完成：正文页累计停留 {sum(plan)} 分钟 ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
