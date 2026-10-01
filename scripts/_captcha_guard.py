"""广告后滑动验证码守护模块（issue：每次广告后都可能出验证码）。
用法:
    from scripts._captcha_guard import check_and_solve
    check_and_solve(client)  # 有验证码就求解并复检，返回 True=已清除/无验证码

修复点:
- PNG 正确编码: Screenshot.save(路径) 落盘后读 bytes（修裸像素 bug）
- detect_slide 失败时回退 OCR 锚定: 用「拖动下方滑块完成拼图」文字行定位
  轨道 y；滑块起点用固定左端 (168, 818)（历史实测）；距离=轨道右端-
  滑块宽 90%（保守两段滑：先 85% 快滑，再回微调）
- 求解后复检，最多 3 轮
"""
from __future__ import annotations

import tempfile
import time
from pathlib import Path

_CAPTCHA_KEYS = ("安全验证", "滑块", "拼图")
_TRACK_HINT = "拖动下方滑块"
_SLIDER_START = (168, 818)  # 历史实测滑块中心
_TEMP_DIR = Path(tempfile.gettempdir())


def _png_bytes(client) -> bytes:
    """Screenshot → PNG bytes（经临时文件，修裸像素 bug）。"""
    s = client.screencap()
    p = _TEMP_DIR / f"guard_cap_{int(time.time()*1000)}.png"
    s.save(str(p))
    data = p.read_bytes()
    p.unlink(missing_ok=True)
    return data


def has_captcha(client) -> bool:
    boxes = client.recognize("OCR", {}, client.screencap()).text_boxes()
    joined = " ".join(t for t, b in boxes)
    return any(k in joined for k in _CAPTCHA_KEYS)


def check_and_solve(client, max_rounds: int = 3) -> bool:
    """返回 True=页面无验证码（或已清掉）；False=3 轮后仍在。"""
    for round_no in range(1, max_rounds + 1):
        if not has_captcha(client):
            return True
        png = _png_bytes(client)
        try:
            from qqreader.captcha.slide import detect_slide
            det = detect_slide(png)
        except Exception as exc:  # opencv 缺失等
            det = None
            print(f"  [guard] detect 异常: {exc}", flush=True)

        if det is not None and det.found and det.distance > 0:
            dist = det.distance
            cy = det.slider_center[1] if det.slider_center else _SLIDER_START[1]
            print(f"  [guard r{round_no}] 几何检测 dist={dist}", flush=True)
        else:
            # OCR 回退：锚定提示行取轨道 y；距离用轨道右端估算法
            boxes = client.recognize("OCR", {}, client.screencap()).text_boxes()
            hint = [(t, b) for t, b in boxes if _TRACK_HINT in t]
            if hint:
                hb = hint[0][1]
                sy = hb[1] + 60  # 滑块在提示行下方
            else:
                sy = _SLIDER_START[1]
            # 历史轨道 (75,806,567,26)：右端 642，滑块行程 ≈ 642-118-75 ≈ 450，
            # 实际成功距离 294/338 → 取行程 68% 保守值
            dist = 300
            cy = sy + 10
            print(f"  [guard r{round_no}] 回退估算 dist={dist} y={cy}", flush=True)

        _human_slide(client, _SLIDER_START[0], cy, dist)
        time.sleep(2.5)

        if not has_captcha(client):
            print(f"  [guard r{round_no}] ✅ 验证码已清除", flush=True)
            return True
        print(f"  [guard r{round_no}] 仍在，重试", flush=True)
    return False


def _human_slide(client, x: int, y: int, dist: int) -> None:
    """两段式拟人滑动：主滑 + 微调回拉。"""
    import subprocess
    adb = r"D:\Program Files\Netease\MuMu Player 12\shell\adb.exe"
    dev = "127.0.0.1:16384"
    # 主滑（sendevent 质量更高，失败退 input swipe）
    try:
        from qqreader.captcha.slide import sendevent_slide
        sendevent_slide(client, x, y, dist)
    except Exception:
        mid = x + int(dist * 0.85)
        subprocess.run([adb, "-s", "127.0.0.1:16384", "shell",
                        f"input swipe {x} {y} {mid} {y} 600"], capture_output=True, timeout=15)
        time.sleep(0.8)
        subprocess.run([adb, "-s", dev, "shell",
                        f"input swipe {mid} {y} {x + dist} {y} 400"], capture_output=True, timeout=15)
