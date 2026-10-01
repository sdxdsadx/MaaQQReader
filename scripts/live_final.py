"""L: 终局实验——坐标修正后的滑动。
按钮真实中心 = 167（暗列法），detect_slide 报的 slider_center=168 几乎一样!
→ 按钮中心没错。缺口暗区中心 = 498（356..641 太宽，可能含拼图块阴影）。
detect_slide 报 gap_x = 168+329 = 497 ≈ 498 一致!!

→ 检测没有问题: 头(按钮)167、缺口498、需滑 331px。
r6 实滑 339px（首滑157+104+78）≈331 目标——**距离已经对准了**!
但 r6 仍「验证错误」→ 拒绝原因只剩两个:
  A. 每次 swipe 是独立的 down-up，验证码要求连续按住拖动（分段 down-up 被
     判为点击+点击）；r2/r6 的「成功滑动」证据（E0 按钮跟手 212→回弹）说明
     单段 swipe 是被识别为拖动的。r6 用 3 段 down-up 拖 → 中途抬起=拼图回弹
     → 每段从新起点累计反而越滑越乱。
  B. 行为轨迹指纹（匀速/过匀）。

修正: **一次连续 swipe 直滑 331px**（r2 已证单段 swipe 跟手），不要分段!
r2 失败是因为当时 distance 检测 206 不对（压字/新题）；现在这题 distance=329
与暗列法 331 互证 → 一次滑 329 必过（若轨迹不是问题）。

立即验证: 直接 client.swipe(168,818, 168+329, 818, 700) 单段一次到底。
"""
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import cv2
import numpy as np

from qqreader.captcha.slide import detect_slide
from qqreader.config import load_config
from qqreader.maa.factory import build_maa_client

ACC = Path(r"G:\project_X\runtime\screenshots\19700104")


def ocr_texts(client):
    s = client.screencap()
    ocr = client.recognize("OCR", {}, s)
    d = ocr.detail if isinstance(ocr.detail, dict) else {}
    items = d.get("all") or d.get("boxes") or d.get("items") or []
    return " ".join(str(i.get("text")) for i in items if isinstance(i, dict))


def main() -> int:
    config = load_config("configs/qqreader.local.json")
    client = build_maa_client(config)
    client.connect()

    # 当前帧检测
    s = client.screencap()
    p = ACC / "liveM_t0.png"
    p.write_bytes(s.data if hasattr(s, "data") else s)
    d = detect_slide(p.read_bytes())
    if not d.found:
        print("[M] 验证码不在屏/检测失败:", d.error)
        client.close()
        return 1
    sx, sy = d.slider_center
    dist = d.distance
    print(f"[M] 起点=({sx},{sy}) 缺口距={dist} → 单段直滑 {dist}px 800ms")
    client.swipe(sx, sy, sx + dist, sy, 800)
    time.sleep(2.5)
    joined = ocr_texts(client)
    ok = "安全验证" not in joined and "滑块" not in joined and "验证" not in joined
    print(f"[M] 结果: {'✅ 通过!!' if ok else '❌ 仍失败'} | 文案: {joined[:100]}")
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
