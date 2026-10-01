"""I: 最终真相——拼图头在容器带 y690..810 内 1:1 移动！
r2: 前 199 → 滑 206 后应为 405。但 r2"后"图左区峰 240 强度骤降(11777→788)
——因为头已经移出左区(>260)。r2 头若在 405，全带峰应在 405 附近。
验证: 全带峰 x。现在帧: 左区峰 235 强度 6409（头可能停在 235?? 但我们没滑对）。

结论已足够: **拼图头 1:1 跟随按钮**（无缩放!），容器带 y690..810 是正确观测带
（不是 600..800）。之前所有「scale 2.14/5.44」都是错带测量的伪影!
r2 的 197→638 = 差分饱和/内容变化误判。

正确求解: head0=199（r2前），gap=? —— 用容器带找缺口。
现在帧: 头 235?（probeF 之前滑过几次没回弹成功？按钮回 109 但头 235 不回?）
不, 头/按钮应同步。矛盾说明容器带 235 的峰不是头而是背景内容。
→ 需要一个不被背景干扰的头部检测: 拼图头=白色描边方块。用白色 mask 而非边缘。
"""
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import cv2
import numpy as np

ACC = _ROOT / "runtime/screenshots/19700104"

for tag, fname in (("r2前", "DailyAdFlow_19700104_042439_843000_003_CAPTCHA_DETECTED.png"),
                   ("r2后", "DailyAdFlow_19700104_041939_562000_013_BLOCKED_BY_CAPTCHA.png"),
                   ("现在", "probeF_end.png")):
    img = cv2.imdecode(np.fromfile(str(ACC / fname), dtype=np.uint8), cv2.IMREAD_COLOR)
    # 白描边: 高亮度 + 低饱和
    hsv = cv2.cvtColor(img[690:812, 60:655], cv2.COLOR_BGR2HSV)
    white = cv2.inRange(hsv, (0, 0, 235), (180, 40, 255))
    cs, _ = cv2.findContours(white, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    heads = []
    for c in cs:
        x, y, cw, ch = cv2.boundingRect(c)
        if 60 <= cw <= 180 and 30 <= ch <= 100 and cv2.contourArea(c) > 800:
            heads.append((60 + x, 690 + y, cw, ch, int(cv2.contourArea(c))))
    print(f"{tag}: 白描边方块候选 = {heads[:4]}")
