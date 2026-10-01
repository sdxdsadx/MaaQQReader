"""单轮活体滑块实验: check(只检测+OCR) / slide [delta] [speed] (检测→sendevent滑→复查)。

用法:
  python _live_round.py check
  python _live_round.py slide          # 按当前检测 dist 滑, 轨迹 mid 档
  python _live_round.py slide 8 fast   # dist+8, 快节奏轨迹
"""
import random
import re
import subprocess
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from qqreader.captcha.slide import detect_slide
from qqreader.config import load_config
from qqreader.maa.factory import build_maa_client

OUT = _ROOT / "runtime" / "screenshots" / "19700105"
CAPTCHA_KEYS = ("安全验证", "拖动下方滑块", "滑块完成拼图")
REWARD_KEYS = ("今日已获赠币", "看小视频领好礼", "玩游戏领赠币", "明日再来", "获奖记录")
SPEED = {
    "fast": (8, 18),
    "mid": (14, 34),
    "slow": (22, 46),
}


def get_touch_dev(adb, dev):
    r = subprocess.run([adb, "-s", dev, "shell", "getevent", "-pl"], capture_output=True, text=True, timeout=20)
    cur = None
    for line in r.stdout.splitlines():
        m = re.search(r"add device \d+: (/dev/input/event\d+)", line)
        if m:
            cur = m.group(1)
        if cur and "ABS_MT_POSITION_X" in line:
            return cur
    return None


def send(adb, dev, tdev, events):
    script = "".join(f"sendevent {tdev} {t} {c} {v}; " for t, c, v in events)
    subprocess.run([adb, "-s", dev, "shell", script], capture_output=True, timeout=20)


def human_track(sx, sy, dx, speed="mid", jitter=2, over=None):
    """拟人轨迹: [(x, y, dt_ms), ...] ease-out + y抖动 + 过冲回调。"""
    lo, hi = SPEED.get(speed, SPEED["mid"])
    over = random.randint(4, 9) if over is None else over
    over = over * (1 if dx > 0 else -1)
    n = max(12, min(40, abs(dx) // 6))
    pts = []
    for i in range(1, n + 1):
        f = i / n
        ease = 1 - (1 - f) ** 2
        pts.append((sx + int(dx * ease), sy + random.randint(-jitter, jitter), random.randint(lo, hi)))
    pts.append((sx + dx + over, sy + random.randint(-1, 1), random.randint(20, 40)))
    pts.append((sx + dx, sy, random.randint(25, 50)))
    return pts


def ocr_texts(client, shot):
    ocr = client.recognize("OCR", {}, shot)
    dd = ocr.detail if isinstance(ocr.detail, dict) else {}
    items = dd.get("all") or dd.get("boxes") or dd.get("items") or []
    return [str(i.get("text", "")) for i in items if isinstance(i, dict)]


def snap(client, tag):
    s = client.screencap()
    data = s.data if hasattr(s, "data") else s
    p = OUT / f"autocap_{tag}.png"
    p.write_bytes(data)
    d = detect_slide(data)
    texts = ocr_texts(client, s)
    joined = " ".join(texts)
    cap_on = any(k in joined for k in CAPTCHA_KEYS)
    reward = any(k in joined for k in REWARD_KEYS)
    return d, texts, cap_on, reward


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else "check"
    delta = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    speed = sys.argv[3] if len(sys.argv) > 3 else "mid"

    config = load_config("configs/qqreader.local.json")
    adb = config.machine.adb_path
    dev = config.machine.adb_address
    client = build_maa_client(config)
    client.connect()
    try:
        d, texts, cap_on, reward = snap(client, "r_pre")
        print(f"[pre] detect={'FOUND' if d.found else d.error} track={d.track} slider={d.slider} center={d.slider_center} dist={d.distance}")
        print(f"[pre] CAPTCHA_ON={cap_on} REWARD_PAGE={reward} n_boxes={len(texts)}")
        if mode != "slide":
            return 0
        if not cap_on:
            print("[pre] 验证码已不在 → 无需滑动")
            return 0
        if not d.found:
            print("[pre] 检测不到轨道 → 本轮不滑")
            return 2

        tdev = get_touch_dev(adb, dev)
        if not tdev:
            print("[!!] 无触屏设备")
            return 1
        sx, sy = d.slider_center
        dx = d.distance + delta
        print(f"[slide] 起点({sx},{sy}) 位移={dx} (dist{d.distance}+delta{delta}) speed={speed} dev={tdev}")
        send(adb, dev, tdev, [(3, 57, 0), (3, 53, sx), (3, 54, sy), (1, 330, 1), (0, 0, 0)])
        time.sleep(0.05)
        for x, y, dt in human_track(sx, sy, dx, speed=speed):
            send(adb, dev, tdev, [(3, 53, x), (3, 54, y), (0, 0, 0)])
            time.sleep(dt / 1000.0)
        time.sleep(random.uniform(0.08, 0.2))
        send(adb, dev, tdev, [(3, 57, -1), (1, 330, 0), (0, 0, 0)])
        print("[slide] 注入完成, 等 2.5s")
        time.sleep(2.5)

        d2, texts2, cap_on2, reward2 = snap(client, "r_post")
        print(f"[post] detect={'FOUND' if d2.found else d2.error} center={d2.slider_center} dist={d2.distance}")
        print(f"[post] CAPTCHA_ON={cap_on2} REWARD_PAGE={reward2}")
        print("[post] OCR:", " | ".join(t[:24] for t in texts2[:14]))
        verdict = "SOLVED" if (not cap_on2 and reward2) else ("GONE_NO_REWARD" if not cap_on2 else "STILL_ON")
        print(f"[verdict] {verdict}")
        return 0 if verdict == "SOLVED" else 3
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
