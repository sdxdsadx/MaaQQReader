from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np


BASE_DIR = Path(__file__).resolve().parent
TEMPLATE_DIR = BASE_DIR / "templates"
ADB = Path(r"D:\Program Files\Netease\MuMu Player 12\shell\adb.exe")
PLAYER = Path(r"D:\Program Files\Netease\MuMu Player 12\shell\MuMuPlayer.exe")
PACKAGE = "com.qq.reader"
DEVICE = "127.0.0.1:16384"
LOG_FILE = BASE_DIR / "自动点击日志.txt"
LAST_SCREEN = BASE_DIR / "最后画面.png"
TIMER_CALLBACK = None
CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def log(message: str) -> None:
    line = f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {message}"
    print(line, flush=True)
    with LOG_FILE.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def set_timer_callback(callback) -> None:
    global TIMER_CALLBACK
    TIMER_CALLBACK = callback


def wait_task(minutes: float, label: str, stop_event=None) -> None:
    seconds = max(1, int(float(minutes) * 60))
    log(f"{label}开始计时：{minutes:g} 分钟。")
    if TIMER_CALLBACK:
        TIMER_CALLBACK("start", label, seconds)
    deadline = time.monotonic() + seconds
    try:
        while time.monotonic() < deadline:
            remaining = deadline - time.monotonic()
            if stop_event is not None:
                if stop_event.wait(timeout=min(1, remaining)):
                    raise InterruptedError("用户已终止任务。")
            else:
                time.sleep(min(1, remaining))
    finally:
        if TIMER_CALLBACK:
            TIMER_CALLBACK("end", label, 0)
    log(f"{label}计时完成。")


def run(command: list[str], *, timeout: float = 30, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=timeout,
        check=check,
        creationflags=CREATE_NO_WINDOW,
    )


def adb(*args: str, timeout: float = 30, check: bool = True) -> subprocess.CompletedProcess:
    return run([str(ADB), "-s", DEVICE, *args], timeout=timeout, check=check)


def connected() -> bool:
    probe = run([str(ADB), "devices"], check=False)
    text = probe.stdout.decode("utf-8", errors="ignore")
    return bool(re.search(rf"^{re.escape(DEVICE)}\s+device\b", text, re.MULTILINE))


def ensure_emulator() -> None:
    if not ADB.is_file() or not PLAYER.is_file():
        raise FileNotFoundError("MuMu Player 12 或 adb 路径不存在。")

    run([str(ADB), "connect", DEVICE], check=False, timeout=8)
    if not connected():
        log("正在启动 MuMu 模拟器……")
        subprocess.Popen(
            [str(PLAYER)],
            cwd=str(PLAYER.parent),
            creationflags=CREATE_NO_WINDOW,
        )

    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        run([str(ADB), "connect", DEVICE], check=False, timeout=8)
        if connected():
            break
        time.sleep(3)
    else:
        raise RuntimeError("120 秒内未连接到 MuMu ADB。")

    size = adb("shell", "wm", "size").stdout.decode("utf-8", errors="ignore")
    if "720x1280" not in size:
        raise RuntimeError(f"模拟器分辨率不是 720×1280：{size.strip()}")
    log("模拟器已连接，分辨率校验通过。")


def screenshot() -> np.ndarray:
    raw = adb("exec-out", "screencap", "-p", timeout=20).stdout
    image = cv2.imdecode(np.frombuffer(raw, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None or image.shape[:2] != (1280, 720):
        raise RuntimeError("无法取得 720×1280 的模拟器截图。")
    return image


def tap(x: int, y: int, label: str = "") -> None:
    if label:
        log(f"点击：{label}")
    adb("shell", "input", "tap", str(int(x)), str(int(y)))


def back(label: str = "返回") -> None:
    log(label)
    adb("shell", "input", "keyevent", "4")


def swipe(x1: int, y1: int, x2: int, y2: int, duration_ms: int = 650) -> None:
    adb(
        "shell", "input", "swipe",
        str(x1), str(y1), str(x2), str(y2), str(duration_ms),
    )


def load_template(filename: str) -> np.ndarray:
    path = TEMPLATE_DIR / filename
    # OpenCV 4.6 在 Windows 上的 imread 对中文路径支持不完整。
    # 先由 Python 读取字节，再交给 OpenCV 解码，可兼容中文目录。
    try:
        template = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)
    except OSError:
        template = None
    if template is None:
        raise FileNotFoundError(f"缺少识别图片：{path}")
    return template


def find_template(
    screen: np.ndarray,
    filename: str,
    threshold: float = 0.72,
    region: tuple[int, int, int, int] | None = None,
) -> tuple[int, int, float] | None:
    template = load_template(filename)
    x0, y0, x1, y1 = region or (0, 0, screen.shape[1], screen.shape[0])
    haystack = screen[y0:y1, x0:x1]
    if haystack.shape[0] < template.shape[0] or haystack.shape[1] < template.shape[1]:
        return None
    result = cv2.matchTemplate(haystack, template, cv2.TM_CCOEFF_NORMED)
    _, score, _, location = cv2.minMaxLoc(result)
    if score < threshold:
        return None
    h, w = template.shape[:2]
    return x0 + location[0] + w // 2, y0 + location[1] + h // 2, float(score)


def wait_and_tap_template(
    filename: str,
    label: str,
    *,
    timeout: float = 25,
    threshold: float = 0.72,
    region: tuple[int, int, int, int] | None = None,
) -> bool:
    deadline = time.monotonic() + timeout
    best_score = 0.0
    while time.monotonic() < deadline:
        screen = screenshot()
        match = find_template(screen, filename, threshold, region)
        if match:
            x, y, score = match
            log(f"识别到 {label}（相似度 {score:.2f}）")
            tap(x, y, label)
            return True
        # 记录一次较低阈值的最佳结果，便于排错，但不点击。
        weak = find_template(screen, filename, 0.35, region)
        if weak:
            best_score = max(best_score, weak[2])
        time.sleep(1)
    log(f"未可靠识别到 {label}（最佳相似度 {best_score:.2f}）")
    return False


def find_blue_play_button(screen: np.ndarray) -> tuple[int, int] | None:
    # AI 朗读页中央按钮为高饱和蓝色圆形。限定区域可避开状态栏等蓝色元素。
    roi = screen[620:980, 180:540]
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, np.array([82, 110, 110]), np.array([115, 255, 255]))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))
    count, _, stats, centers = cv2.connectedComponentsWithStats(mask)
    candidates: list[tuple[int, float, int, int]] = []
    for index in range(1, count):
        x, y, w, h, area = stats[index]
        if 1500 <= area <= 16000 and 0.70 <= w / max(h, 1) <= 1.35:
            cx, cy = centers[index]
            candidates.append((int(area), abs(cx - 180), int(cx) + 180, int(cy) + 620))
    if not candidates:
        return None
    _, _, x, y = sorted(candidates, key=lambda item: (-item[0], item[1]))[0]
    return x, y


def start_qqreader() -> None:
    log("启动 QQ 阅读。")
    result = adb(
        "shell", "am", "start", "-W", "-n",
        "com.qq.reader/.activity.DefaultAliasActivity",
        timeout=45,
    )
    output = result.stdout.decode("utf-8", errors="ignore")
    if "Status: ok" not in output and "Warning: Activity not started" not in output:
        raise RuntimeError(f"QQ 阅读启动失败：{output.strip()}")
    time.sleep(12)


def ensure_bookshelf(timeout: float = 20) -> None:
    """通过封面识别回到书架，避免模块重复运行时从错误页面开始。"""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        screen = screenshot()
        listen = find_template(screen, "listen_book.png", 0.68, (0, 220, 520, 1180))
        reading = find_template(screen, "read_book.png", 0.68, (0, 220, 520, 1180))
        if listen or reading:
            log("已通过图片识别确认当前位于书架。")
            return
        back("尝试返回书架")
        time.sleep(2)
    raise RuntimeError("未能通过图片识别返回书架。")


def prepare_qqreader() -> None:
    """让任意任务模块都可脱离固定顺序独立、重复执行。"""
    ensure_emulator()
    try:
        screen = screenshot()
        on_shelf = (
            find_template(screen, "listen_book.png", 0.68, (0, 220, 520, 1180))
            or find_template(screen, "read_book.png", 0.68, (0, 220, 520, 1180))
        )
        if on_shelf:
            log("QQ 阅读已在书架，无需重复启动。")
            return
    except Exception:
        pass
    start_qqreader()
    ensure_bookshelf()


def daily_game(duration_minutes: float = 25, stop_event=None) -> None:
    log("执行每日游戏入口流程。")
    prepare_qqreader()
    tap(250, 185, "赠币任务入口")

    # 冷启动时任务页可能会长时间显示白色加载画面。先确认中央内容区
    # 已经出现文字/卡片，再开始滚动，避免在空白页上提前用完重试次数。
    page_deadline = time.monotonic() + 90
    while time.monotonic() < page_deadline:
        screen = screenshot()
        _, content_std = cv2.meanStdDev(screen[120:1160, 20:700])
        if float(content_std.max()) >= 12.0:
            log("赠币任务页已完成加载。")
            break
        time.sleep(2)
    else:
        raise RuntimeError("赠币任务页持续为空白，等待90秒后停止。")

    game_match = None
    for _ in range(8):
        screen = screenshot()
        game_match = find_template(
            screen,
            "game_task.png",
            0.68,
            (20, 120, 520, 1160),
        )
        if game_match:
            break
        swipe(360, 1110, 360, 390)
        time.sleep(1)
    if not game_match:
        raise RuntimeError("未识别到“玩游戏领赠币”任务，已停止以免进入错误界面。")
    _, game_y, game_score = game_match
    log(f"识别到“玩游戏领赠币”任务（相似度 {game_score:.2f}）")
    tap(592, game_y, "正确的去玩游戏按钮")
    try:
        # QQ 阅读存在两种跳转：冷启动时可能直接进入游戏，热启动时则
        # 先进入游戏中心。这里同时识别两种情况，避免等待错误的中间页。
        center_match = None
        running = None
        center_deadline = time.monotonic() + 90
        while time.monotonic() < center_deadline:
            screen = screenshot()
            running = find_template(
                screen,
                "game_exit_tab.png",
                0.55,
                (590, 120, 720, 500),
            )
            if running:
                log("任务入口已直接打开游戏，无需点击游戏中心轮播图。")
                break
            center_match = find_template(
                screen,
                "game_center_ready.png",
                0.55,
                (0, 600, 720, 930),
            )
            if center_match:
                break
            time.sleep(2)
        if not center_match and not running:
            raise RuntimeError("既未识别到游戏中心，也未识别到已打开的游戏。")
        if center_match:
            log(f"已识别游戏中心（相似度 {center_match[2]:.2f}）。")
            tap(360, 400, "当前游戏轮播图")

        # 游戏种类可以变化，但 QQ 阅读游戏容器右侧的红色退出控件固定。
        # 识别到该控件才说明已真正进入游戏，此时再开始任务计时。
        best_score = running[2] if running else 0.0
        if not running:
            deadline = time.monotonic() + 90
            while time.monotonic() < deadline:
                screen = screenshot()
                running = find_template(
                    screen,
                    "game_exit_tab.png",
                    0.55,
                    (590, 120, 720, 500),
                )
                if running:
                    best_score = running[2]
                    break
                weak = find_template(
                    screen,
                    "game_exit_tab.png",
                    0.35,
                    (590, 120, 720, 500),
                )
                if weak:
                    best_score = max(best_score, weak[2])
                time.sleep(2)
            else:
                raise RuntimeError(
                    "点击轮播图后未识别到游戏退出控件，"
                    f"已停止计时（最佳相似度 {best_score:.2f}）。"
                )
        log(f"已确认进入游戏（相似度 {best_score:.2f}），现在开始计时。")
        wait_task(duration_minutes, "每日游戏", stop_event)
    finally:
        tap(704, 300, "游戏侧边退出按钮")
        time.sleep(1)
        tap(585, 295, "退出游戏")
        time.sleep(5)
        back("返回赠币任务页")
        time.sleep(3)
        back("返回书架")
        time.sleep(4)
        ensure_bookshelf()


def daily_listening(duration_minutes: float = 25, stop_event=None) -> None:
    log("开始图片识别：每日听书。")
    prepare_qqreader()
    if not wait_and_tap_template(
        "listen_book.png", "《全职法师》封面", region=(0, 250, 500, 1100)
    ):
        raise RuntimeError("书架中未找到每日听书用书，已停止以免误点。")
    time.sleep(6)

    deadline = time.monotonic() + 25
    while time.monotonic() < deadline:
        screen = screenshot()
        point = find_blue_play_button(screen)
        if point:
            tap(*point, "AI 朗读播放按钮")
            time.sleep(3)
            try:
                wait_task(duration_minutes, "每日听书", stop_event)
            finally:
                tap(*point, "停止 AI 朗读")
                time.sleep(1)
                back("退出听书界面并返回书架")
                time.sleep(4)
            return
        time.sleep(1)
    raise RuntimeError("未识别到 AI 朗读播放按钮，已停止以免误点。")


def daily_reading(duration_minutes: float = 25, stop_event=None) -> None:
    log("开始图片识别：每日阅读。")
    prepare_qqreader()
    if not wait_and_tap_template(
        "read_book.png", "《宇智波：从扉间人柱力开始》封面", region=(0, 250, 500, 1150)
    ):
        raise RuntimeError("书架中未找到每日阅读用书，已停止以免误点。")
    time.sleep(7)

    # 点击正文中央显示阅读工具栏；此动作只有在书籍封面识别成功后才执行。
    tap(360, 600, "显示阅读工具栏")
    time.sleep(2)
    if not wait_and_tap_template(
        "reading_settings.png",
        "阅读设置",
        timeout=8,
        threshold=0.60,
        region=(330, 1120, 550, 1280),
    ):
        raise RuntimeError("未识别到阅读设置，已停止以免误点。")
    time.sleep(2)
    if not wait_and_tap_template(
        "auto_read.png",
        "自动阅读",
        timeout=8,
        threshold=0.58,
        region=(200, 1010, 520, 1210),
    ):
        raise RuntimeError("未识别到自动阅读按钮，已停止以免误点。")
    time.sleep(3)
    log("自动阅读已启动。")
    try:
        wait_task(duration_minutes, "每日阅读", stop_event)
    finally:
        tap(360, 600, "显示自动阅读工具栏")
        time.sleep(1)
        back("退出自动阅读")
        time.sleep(2)
        back("返回书架")
        time.sleep(3)
        ensure_bookshelf()


def wait_until(end_time: float) -> None:
    while True:
        remaining = int(end_time - time.monotonic())
        if remaining <= 0:
            return
        minutes, seconds = divmod(remaining, 60)
        print(f"\r剩余时间：{minutes:02d}:{seconds:02d}", end="", flush=True)
        time.sleep(min(10, remaining))


def close_emulator() -> None:
    log("计时结束，关闭 QQ 阅读和 MuMu 模拟器。")
    adb("shell", "am", "force-stop", PACKAGE, check=False)
    subprocess.run(
        ["taskkill", "/F", "/T", "/IM", "MuMuPlayer.exe"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
        creationflags=CREATE_NO_WINDOW,
    )


def validate_assets() -> None:
    for filename in (
        "game_task.png",
        "game_center_ready.png",
        "game_exit_tab.png",
        "listen_book.png",
        "read_book.png",
        "reading_settings.png",
        "auto_read.png",
    ):
        load_template(filename)
    if not ADB.is_file() or not PLAYER.is_file():
        raise FileNotFoundError("MuMu Player 12 路径校验失败。")
    log("环境和识别图片校验通过。")


def main() -> int:
    parser = argparse.ArgumentParser(description="QQ 阅读 + MuMu 自动任务")
    parser.add_argument("--minutes", type=float, default=25, help="每个计时任务单次运行多少分钟")
    parser.add_argument("--check", action="store_true", help="只做环境校验，不点击")
    parser.add_argument("--skip-game", action="store_true", help="跳过每日游戏入口流程")
    args = parser.parse_args()

    validate_assets()
    if args.check:
        return 0

    try:
        ensure_emulator()
        log("模拟器启动后等待 10 秒。")
        time.sleep(10)
        start_qqreader()
        log("QQ 阅读启动后等待 8 秒。")
        time.sleep(8)
        if not args.skip_game:
            daily_game(args.minutes)
        daily_listening(args.minutes)
        daily_reading(args.minutes)
        close_emulator()
        log("全部完成。")
        return 0
    except KeyboardInterrupt:
        log("用户取消了脚本；没有自动关闭模拟器。")
        return 130
    except Exception as exc:
        log(f"发生错误：{exc}")
        try:
            encoded, buffer = cv2.imencode(".png", screenshot())
            if encoded:
                buffer.tofile(LAST_SCREEN)
            log(f"已保存排错画面：{LAST_SCREEN}")
        except Exception:
            pass
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
