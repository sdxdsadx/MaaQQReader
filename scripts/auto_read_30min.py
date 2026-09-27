"""自动阅读脚本（以老版本 `_run_direct_reading` 为样本重构）。

## 为什么这样设计

老版本（备份 `gui/maa_qq_reader_gui.py:71-74`）的结论：

> QQ 阅读正文页启用 FLAG_SECURE，不能把"自动阅读"按钮是否响应作为唯一成功
> 条件。每段停留不超过 15 分钟，返回书架后重新进书，确保即使自动翻页失效
> 也能稳定累计在线阅读时长。

本脚本按老版本重建，**不回读正文页**：

1. 总时长切成 ≤ `SEGMENT_MINUTES`（默认 15）的段，每段重新进书 —— 保证服务端
   稳定累计时长，且单段失败只损失一段。
2. 每段的动作链：启动 App → 关拦路弹窗 → 回书架 → OCR 识别目标书并点击 →
   等 `ReaderPageActivity` → 盲点「自动阅读」（best-effort）→ 按分钟 dwell 计时
   → 返回可截图页面。
3. **唯一成功判据：`ReaderPageActivity` 停留满本段时长。** 不依赖按钮响应、
   toast、翻页证据。
4. 目标书由书架 OCR 选定，所以不需要「事后扫正文页顶部 OCR 白名单」这种校不到
   实处的校验 —— 选书本身就是白名单。

## 2026-09-21 实机修正（两处关键缺陷）

* **界面判据换通道**：原实现用 `uiautomator dump` 找「书架」文本。但 QQ 阅读主界面
  是 Flutter，渲染成单层 canvas，dump 出来 **没有任何 text 节点**（实测返回空），
  于是 `return_to_shelf` 必然抛「未能回到 QQ 阅读书架」。改用 **Maa 截图 + OCR**
  后，「书架」可稳定读到。附带好处：Maa 截图走独立通道，不像裸 adb 那样依赖
  「命令一结束就被回收的 adb server」。
* **封面模板这条路废弃**：`reading_target_uchiha_cover.png` 实测是**正文页截图**
  （FLAG_SECURE 下抓出来是空白/损坏图），对书架封面做 TemplateMatch 恒为
  `hit=False score=None`。改为**全屏 OCR 精确匹配书名**，实测稳定命中：
  `'宇智波：从扉间人柱力开始' box=(138, 590, 310, 27)`。
* **新增拦路弹窗处理**：实测会上三种弹窗，原脚本全无处理 ——
  升级提示「安装新版本/已下载新版本，是否安装？」、退出确认「确定退出QQ阅读？」、
  运营活动弹窗。统一由 `dismiss_blocking_dialogs()` 点「取消/关闭」类按钮处理，
  **绝不点确认类**，保证不改变被测环境（尤其不点「安装」造成版本变更）。

目标书与识别参数见下方 `TARGET_*` 常量。

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
from datetime import datetime
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    _reconfigure = getattr(_stream, "reconfigure", None)
    if _reconfigure is not None:
        _reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from qqreader.config import load_config

LOG = ROOT / "runtime" / "logs" / "auto_read.log"

# 老版本 DIRECT_READING_DWELL_SEGMENT_MINUTES
SEGMENT_MINUTES = 15

# 目标书识别（与 pipeline ReadingFindBook / ReadingFindBookByTitleTerminal 对齐）
#
# 注意：`reading_target_uchiha_cover.png` 已废弃 —— 实测该文件是**正文页截图**
# （FLAG_SECURE 下抓出来是空白/损坏图），对书架封面做 TemplateMatch 永远 score=0
# （2026-09-21 实测 hit=False score=None）。因此模板匹配这条路彻底移除，
# 改为「全屏 OCR 精确匹配书名」，实测在书架上稳定命中：
#   '宇智波：从扉间人柱力开始' box=(138, 590, 310, 27)
TARGET_TITLE_PATTERN = r"宇智波.*扉间人柱力|宇智波：从扉间人柱力开始"

# 书架页判据。
#
# **不能只用「书架」二字**：底部导航栏的「书架」tab 在书城/发现/广场等**所有**
# 页面都存在，用它判断恒为 True，判据形同虚设。2026-09-21 实测就是这样：
# 流程卡在「广场」（社区书评页），OCR 读到书评文本，但 `is_on_shelf()` 因为
# 底部 tab 有「书架」而误判成功，随后书源校验才把它拦下（幸好守门有效）。
#
# 改用**书架页独有**的文本：顶部时长区/笔记/书籍进度行。
SHELF_ONLY_MARKERS = (
    "本周未开始阅读",
    "再读",          # 「再读 8 分钟领 20 赠币」
    "时长兑赠币",     # 「时长兑赠币，立即领取」
    "我的笔记",
)
# 书籍进度行，如「84章/372章」「25章/543章·更新至…」。QQR-55：旧判据是子串
# 「章/」，2026-09-27 误中书城活动横幅「勋章/装扮限时返场」，把排行榜页当成书架。
SHELF_PROGRESS_PATTERN = re.compile(r"\d+章/\d+章")
# 明显不属于书架的页面特征（出现即判定不在书架）
NON_SHELF_MARKERS = (
    "关注", "广场", "一键三连",
    "分享", "热门话题", "回复",
)
# 书城首页/排行榜的频道与榜单文案；命中 2 个以上即判定为书城，不是书架。
BOOKSTORE_MARKERS = ("男生", "女生", "排行榜", "本周强推", "今日必读", "高分必读")
# 回书架时确认不了页面的受控重试次数（每次都重新截图确认）。
SHELF_CONFIRM_ATTEMPTS = 3
# 底部导航栏的最小 y（720×1280；书架 tab OCR box=(70,1250,38,26)）。
BOTTOM_NAV_MIN_Y = 1150

# 进正文后盲点「自动阅读」三连（老版本 _run_direct_reading 原值，best-effort）
AUTO_READ_TAPS = ((360, 640), (450, 1214), (360, 1125))

PACKAGE = "com.qq.reader"
READER_ACTIVITY = "ReaderPageActivity"

# --- 拦路弹窗（2026-09-21 实测新增，脚本原先完全没有处理）---
# 1) QQ 阅读 V8.5.6 升级提示：「安装新版本 / 已下载新版本，是否安装？」
#    按钮「安装」在左半 (0,1205,360,1280)、「取消」在右半 (360,1205,720,1280)
UPGRADE_DIALOG_MARKERS = ("安装新版本", "已下载新版本", "是否安装")
# 2) 退出确认：「确定退出QQ阅读？」 取消 (510,1226,56,31)
EXIT_DIALOG_MARKERS = ("退出QQ阅读", "退出 QQ 阅读", "退出软件", "确定退出", "是否退出")
EXIT_DIALOG_CANCELS = {"取消", "暂不退出", "继续使用"}
# 3) 活动弹窗（中秋等运营活动），点右上角 X 关闭
ACTIVITY_DIALOG_MARKERS = ("限时返场", "免费读一年", "活动书单", "找兔子")
# 关闭类按钮文本（点这些不会改变被测环境），按优先级排列：弹窗自带的「取消 / 暂不」优先于页面上可能存在的「X」。
# 以前是 set，tuple(set) 的顺序随进程哈希随机，升级弹窗叠在书城页上时可能先点到 X。
DISMISS_TEXTS = ("取消", "暂不", "以后再说", "关闭", "×", "X", "x", "跳过")

_client = None
_adb_path = ""
_adb_address = ""
# 失败现场截图目录（来自配置 machine.screenshot_dir）。
_evidence_dir: Path | None = None


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


def ocr_boxes() -> list[tuple[str, tuple[int, int, int, int]]]:
    """用 Maa 截图 + OCR 取全屏文本框。

    为什么不用 uiautomator：QQ 阅读主界面是 Flutter，渲染成单层 canvas，
    `uiautomator dump` 拿不到任何 text 节点（实测返回空），因此原先基于
    UI 层级的「书架」判据必然失败。而 **截图通道是好的**（书架页可截图），
    OCR 能稳定读出「书架」「宇智波：从扉间人柱力开始」等文本。

    Maa 的截图/OCR 走独立通道，不依赖会随命令结束而消失的 adb server，
    比裸 adb 更可靠。
    """
    if _client is None:
        return []
    try:
        shot = _client.screencap()
        result = _client.recognize("OCR", {}, shot)
        return list(result.text_boxes())
    except Exception as exc:  # noqa: BLE001 - OCR 失败按「读不到」处理
        log(f"OCR 读取失败：{exc}")
        return []


def find_text(
    boxes: list[tuple[str, tuple[int, int, int, int]]], needle: str
) -> tuple[str, tuple[int, int, int, int]] | None:
    """在 OCR 结果里找包含 needle 的框（忽略空白差异）。"""
    compact = needle.replace(" ", "")
    for text, box in boxes:
        if compact and compact in text.replace(" ", ""):
            return text, box
    return None


def find_any(
    boxes: list[tuple[str, tuple[int, int, int, int]]], needles: tuple[str, ...]
) -> tuple[str, tuple[int, int, int, int]] | None:
    for needle in needles:
        hit = find_text(boxes, needle)
        if hit is not None:
            return hit
    return None


def tap_box(box: tuple[int, int, int, int]) -> None:
    """点 OCR 框中心。box 是 (x, y, w, h)。"""
    x, y, w, h = box
    tap(x + w // 2, y + h // 2)


def dismiss_blocking_dialogs() -> int:
    """关掉拦路弹窗，返回关闭数量。

    三类（2026-09-21 实机遇全）：
      1. 升级提示「安装新版本 / 已下载新版本，是否安装？」—— 必须点「取消」，
         不能点「安装」，否则会改动被测环境版本。
      2. 退出确认「确定退出QQ阅读？」—— 点「取消」。
      3. 运营活动弹窗（中秋找玉兔等）—— 点右上角 X。

    只点「取消 / 关闭」类按钮，绝不点确认类，保证不改变被测环境。
    """
    closed = 0
    for _ in range(3):  # 可能连续弹多个
        boxes = ocr_boxes()
        if not boxes:
            return closed
        all_text = " ".join(t for t, _ in boxes)

        # 书城页的横幅本身就写着「勋章/装扮限时返场」「免费读一年」，不是弹窗。
        # 2026-09-27 实机：把它当活动弹窗后，在书城页盲点 (307,764) / 点任意「X」。
        activity = (
            any(m in all_text for m in ACTIVITY_DIALOG_MARKERS)
            and classify_page(boxes) != "书城"
        )
        is_dialog = (
            any(m in all_text for m in UPGRADE_DIALOG_MARKERS)
            or any(m in all_text for m in EXIT_DIALOG_MARKERS)
            or activity
        )
        if not is_dialog:
            return closed

        hit = find_any(boxes, DISMISS_TEXTS)
        if hit is None:
            # 活动弹窗有时只有图形 X，没有文本：退到右上角固定点
            if activity:
                tap(307, 764)
                log("活动弹窗未见关闭文本，已点右上角关闭位")
                closed += 1
                time.sleep(2.0)
                continue
            log(f"检测到弹窗但找不到关闭按钮：{all_text[:80]!r}")
            return closed

        text, box = hit
        tap_box(box)
        log(f"已关闭拦路弹窗（点「{text}」）")
        closed += 1
        time.sleep(2.0)
    return closed


def dismiss_exit_dialog() -> bool:
    """兼容旧调用：QQ 阅读按返回键偶尔弹「退出QQ阅读」，点取消。"""
    boxes = ocr_boxes()
    if not boxes:
        return False
    all_text = " ".join(t for t, _ in boxes)
    if not any(marker in all_text for marker in EXIT_DIALOG_MARKERS):
        return False
    hit = find_any(boxes, tuple(EXIT_DIALOG_CANCELS))
    if hit is None:
        return False
    text, box = hit
    tap_box(box)
    log(f"检测到退出确认弹窗，已点「{text}」")
    return True


def return_to_capturable(max_backs: int = 6) -> None:
    """离开 FLAG_SECURE 正文页，回到 Maa 能截图的页面。

    实测路径（2026-09-21）：从正文页按返回，第一次退出阅读器回到 App 主页；
    此时若继续按返回会弹「确定退出QQ阅读？」。**弹出该确认框本身就是
    「已经在 App 主页、已可截图」的信号** —— 所以撞到它就点「取消」收手，
    而不是继续按返回（原实现把每次返回都当"要退 App"，连点 6 次后误判失败）。
    """
    if capture_available():
        return
    for attempt in range(1, max_backs + 1):
        press_back()
        time.sleep(1.8)
        # 出现退出确认框 = 已退到 App 主页（可截图），点取消即可
        if dismiss_exit_dialog():
            time.sleep(1.2)
            if capture_available():
                log(f"已返回可截图页面（返回 {attempt} 次，已取消退出确认）")
                return
            continue
        if capture_available():
            log(f"已返回可截图页面（返回 {attempt} 次）")
            return
    raise RuntimeError("多次返回后 QQ 阅读仍禁止截图")


def is_on_shelf() -> bool:
    """当前是否停在书架页。

    判据必须用**书架页独有**的文本：底部导航栏的「书架」tab 在所有页面都存在，
    单看它会把书城/广场等页面误判成书架（2026-09-21 实测踩过）。
    同时，命中任何 `NON_SHELF_MARKERS` 的社区/发现类页面特征即直接否定。
    """
    return classify_page(ocr_boxes()) == "书架"


def classify_page(boxes: list[tuple[str, tuple[int, int, int, int]]]) -> str:
    """把一帧 OCR 归为「书架 / 书城 / 其他 / 无文本」，供判定和失败记录共用。"""
    if not boxes:
        return "无文本"
    texts = [t.replace(" ", "") for t, _ in boxes]
    joined = " ".join(texts)
    if any(marker in joined for marker in NON_SHELF_MARKERS):
        return "其他"
    if sum(marker in joined for marker in BOOKSTORE_MARKERS) >= 2:
        return "书城"
    if any(marker in joined for marker in SHELF_ONLY_MARKERS):
        return "书架"
    if any(SHELF_PROGRESS_PATTERN.search(text) for text in texts):
        return "书架"
    return "其他"


def go_to_shelf_tab(boxes: list[tuple[str, tuple[int, int, int, int]]] | None = None) -> bool:
    """点底部导航栏里 OCR 实际看到的「书架」tab，返回是否判定为书架。

    看不到底部 tab（排行榜等二级页）就不点：旧实现按固定坐标 (89,1242) 盲点，
    2026-09-27 实机在排行榜二级页上点到的是空白处。
    """
    if boxes is None:
        boxes = ocr_boxes()
    tab = next(
        (box for text, box in boxes if text.strip() == "书架" and box[1] >= BOTTOM_NAV_MIN_Y),
        None,
    )
    if tab is None:
        log("未看到底部「书架」tab，不点击")
        return False
    x, y, w, h = tab
    tap(x + w // 2, y + h // 2)
    time.sleep(2.5)
    dismiss_blocking_dialogs()
    return is_on_shelf()


def return_to_shelf(max_backs: int = 4) -> None:
    """确保停在书架页（而不是同样可截图的奖励页/书城页/广场页）。"""
    return_to_capturable(max_backs=max_backs + 2)
    dismiss_blocking_dialogs()
    for attempt in range(0, max_backs + 1):
        boxes = ocr_boxes()
        page = classify_page(boxes)
        if page == "书架":
            if attempt:
                log(f"已返回书架（额外返回 {attempt} 次）")
            return
        if page == "书城":
            # 书城是主页 tab，返回键只会弹「确定退出」；直接点书架 tab 并重新确认。
            if go_to_shelf_tab(boxes):
                log("书城页 → 已点底部「书架」tab 并确认书架")
                return
        if attempt >= max_backs:
            break
        press_back()
        time.sleep(1.5)
        dismiss_blocking_dialogs()
    # 兜底：返回键在「广场/发现」等 tab 上不切页，必须点底部「书架」tab
    if go_to_shelf_tab():
        log("已通过底部「书架」tab 回到书架")
        return
    raise RuntimeError("未能回到 QQ 阅读书架")


# ------------------------------------------------------------- 选书与计时


class BookNotAllowed(RuntimeError):
    """书架上找不到白名单书目 —— 不静默继续，由 main 以 exit(3) 退出。"""


ALLOWED_BOOK_KEYWORDS = ("宇智波",)


def record_page_evidence(reason: str, boxes: list[tuple[str, tuple[int, int, int, int]]]) -> None:
    """失败现场：页面类型、完整 OCR 与截图（QQR-55：不能只留下 exit 3）。"""
    page = classify_page(boxes)
    full = " | ".join(t for t, _ in boxes) or "（无文本）"
    log(f"现场记录：{reason}；页面类型={page}；完整 OCR：{full}")
    if _client is None or _evidence_dir is None:
        return
    try:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        target = _evidence_dir / "auto_read" / f"{stamp}_{page}.png"
        target.parent.mkdir(parents=True, exist_ok=True)
        _client.screencap().save(target)
        log(f"现场截图：{target}")
    except Exception as exc:  # noqa: BLE001 - 证据失败不改变结论
        log(f"现场截图保存失败：{exc}")


def confirm_allowed_book_on_shelf(attempts: int = SHELF_CONFIRM_ATTEMPTS) -> str:
    """先确认真的在书架，再做白名单校验（QQR-55）。

    * 确认在书架但没有白名单书目 → ``BookNotAllowed``（exit 3，白名单保护不放宽）；
    * 受控次数内始终确认不了书架 → ``RuntimeError``（exit 2），不当成白名单拒绝；
    * 每次都重新截图确认，不盲点其他书。
    """
    boxes: list[tuple[str, tuple[int, int, int, int]]] = []
    page = "无文本"
    for attempt in range(1, attempts + 1):
        boxes = ocr_boxes()
        page = classify_page(boxes)
        if page == "书架":
            box, why = locate_allowed_book_ui(boxes)
            if box is not None:
                return why
            record_page_evidence("书架上没有白名单书目", boxes)
            raise BookNotAllowed(why)
        log(f"第 {attempt}/{attempts} 次确认：当前页面是「{page}」不是书架，回书架后重新确认")
        dismiss_blocking_dialogs()
        try:
            return_to_shelf()
        except RuntimeError as exc:
            log(f"回书架未成功：{exc}")
    record_page_evidence("多次回书架后仍无法确认书架", boxes)
    raise RuntimeError(f"{attempts} 次回书架后仍无法确认书架（最后页面：{page}）")


def locate_allowed_book_ui(
    boxes: list[tuple[str, tuple[int, int, int, int]]] | None = None,
) -> tuple[tuple[int, int, int, int] | None, str]:
    """在书架上用 OCR 定位白名单书目，返回 (box 或 None, 说明)。

    判定依据是 **书架上 OCR 到的书名**，不是正文页顶部 OCR —— 正文页顶部只显示
    章标题，用它判定会误拒正确书目（2026-09-15 实测：同一本《宇智波：从扉间人柱力
    开始》，章首能过、正文中段被误判为"不在白名单"）。

    实测（2026-09-21）：书架页 OCR 稳定返回
        '宇智波：从扉间人柱力开始' box=(138, 590, 310, 27)
    """
    if boxes is None:
        boxes = ocr_boxes()
    if not boxes:
        return None, "OCR 未读到任何文本"
    hit = find_text(boxes, "宇智波")
    if hit is not None:
        text, box = hit
        return box, f"书架书名 OCR {text!r}"
    sample = " | ".join(t for t, _ in boxes[:8]) or "未识别到书名"
    return None, f"书架未识别到白名单书目（允许：{'/'.join(ALLOWED_BOOK_KEYWORDS)}）：{sample!r}"


def _verify_book_allowed(client=None) -> tuple[bool, str]:
    """书源校验：书架上的目标书是否属于自动阅读白名单。"""
    box, message = locate_allowed_book_ui()
    if box is None:
        return False, f"当前书不在自动阅读白名单: {message}"
    return True, message


def click_target_book(max_attempts: int = 3) -> None:
    """在书架上确认白名单书目并点击；点击后不再截图。

    判定与点击用的是同一份 OCR 结果，所以 **不可能**点到白名单以外的书
    —— 选书本身就是守门。多次仍识别不到白名单书目时抛 `BookNotAllowed`，
    由 main 以 exit(3) 退出、不静默继续。
    """
    last = ""
    for attempt in range(1, max_attempts + 1):
        dismiss_blocking_dialogs()
        hit_box, message = locate_allowed_book_ui()
        if hit_box is None:
            last = message
            log(f"第 {attempt}/{max_attempts} 次：{message}，回到书架后重试")
            try:
                return_to_shelf()
            except RuntimeError:
                press_back()
                time.sleep(2.0)
            continue

        tap_box(hit_box)
        log(f"已点击白名单书目（{message}）box={hit_box}")
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
    global _client, _adb_path, _adb_address, _evidence_dir
    parser = argparse.ArgumentParser(description="QQ 阅读自动阅读（dwell 计时）")
    parser.add_argument("--minutes", type=int, default=30, help="总阅读时长（分钟）")
    parser.add_argument("--config", type=Path, default=ROOT / "configs" / "qqreader.local.json",
                        help="本机配置文件")
    parser.add_argument("--segment-minutes", type=int, default=SEGMENT_MINUTES,
                        help="单段停留上限，默认 15（老版本值）")
    parser.add_argument("--skip-claim", action="store_true",
                        help="完成阅读后不自动领取每日阅读奖励")
    args = parser.parse_args()
    if args.minutes < 1:
        log("--minutes 必须 >= 1")
        return 2

    config = load_config(args.config)
    _adb_path = config.machine.adb_path
    _adb_address = config.machine.adb_address
    _evidence_dir = Path(config.machine.screenshot_dir)
    # 界面判据与选书改走 Maa 截图 + OCR：QQ 阅读主界面是 Flutter，
    # uiautomator 拿不到 text 节点（实测返回空）；Maa 截图通道正常且
    # 不依赖会随命令结束消失的 adb server。
    from qqreader.maa.factory import build_maa_client

    _client = build_maa_client(config)
    _client.connect()
    log("Maa 通道已连接（截图 + OCR 可用）")

    plan = segments_for(args.minutes, args.segment_minutes)
    log(f"=== 自动阅读 {args.minutes} 分钟开始（{len(plan)} 段：{plan}）===")

    try:
        return_to_capturable()
        for index, dwell_minutes in enumerate(plan, start=1):
            log(f"--- 第 {index}/{len(plan)} 段：{dwell_minutes} 分钟 ---")
            launch_app()
            time.sleep(3.0)
            dismiss_blocking_dialogs()
            return_to_shelf()
            why = confirm_allowed_book_on_shelf()
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
        log(f"❌ 书源校验/选书失败（exit 3）：{exc}")
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
    if not args.skip_claim:
        claim = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "run_task.py"),
                "--config",
                str(ROOT / "configs" / "qqreader.local.json"),
                "--task",
                "ClaimOneReward",
                "--timeout-minutes",
                "10",
            ],
            cwd=str(ROOT),
            timeout=12 * 60,
            check=False,
        )
        if claim.returncode != 0:
            log(f"❌ 阅读完成，但自动领取奖励失败（exit={claim.returncode}）")
            return 4
        log("阅读奖励自动领取/已领取状态验证成功")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
