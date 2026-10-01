"""r6 判读: 补滑机制工作了（首滑157+补104+78=339 总滑）但「验证错误」。

证据整理（6 轮实测汇总）:
- 轨道 (225,810,414,20)，蓝色按钮宽 118（中心跟随滑动）
- r2: 匀速 206 → 拼图头 197→638（差分实测），缺口 Canny 峰 372-376
- r5: scale=2.14 滑 178 → 失败「已更换题目」（页面换了题!）
- r6: raw=337 → 首滑 157 → 截图后补 104 → 再补 78，总 339 → 「验证错误」

关键矛盾: r2 差分测得拼图头位移/按钮位移 = 441/206 = 2.14，但这个「2.14」
其实可能不是缩放，而是 r2 那次滑动后**拼图头撞到轨道右端被弹回/页面刷新**
——不可靠。而 r6 的迭代补滑在「每次截图 detect 到的按钮位置」上叠加位移，
按钮本身 1:1 跟手 → head_now 计算里的 (total×(scale-1))/scale 项把补偿
越算越乱。

停止猜测。直接看 r6 滑动后截图里拼图头到底在哪:
用差分（r6 CAPTCHA_DETECTED vs BLOCKED）测拼图头真实位移 vs 按钮位移 339。
"""
from pathlib import Path

import cv2
import numpy as np

acc = Path(r"G:\project_X\runtime\screenshots\19700104")
before = cv2.imdecode(np.fromfile(acc / "DailyAdFlow_19700104_044703_656000_003_CAPTCHA_DETECTED.png", dtype=np.uint8), cv2.IMREAD_COLOR)
after = cv2.imdecode(np.fromfile(acc / "DailyAdFlow_19700104_044703_656000_004_BLOCKED_BY_CAPTCHA.png", dtype=np.uint8), cv2.IMREAD_COLOR)

# 按钮位移: 蓝色按钮中心
for tag, im in (("前", before), ("后", after)):
    blue = cv2.inRange(im, (180, 50, 0), (255, 220, 180))
    blue = cv2.morphologyEx(blue, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    cs, _ = cv2.findContours(blue, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    best = None
    for c in cs:
        x, y, cw, ch = cv2.boundingRect(c)
        if cv2.contourArea(c) > 3000 and 60 <= cw <= 180:
            best = (x + cw // 2, y + ch // 2)
            break
    print(f"{tag}: 蓝按钮中心 = {best}")

# 拼图头位移: 拼图区 y600..800 最强竖边缘
for tag, im in (("前", before), ("后", after)):
    g = cv2.cvtColor(im[600:800, :], cv2.COLOR_BGR2GRAY)
    e = cv2.Canny(g, 50, 150)
    col = e.sum(axis=0) / e.shape[0]
    sm = np.convolve(col, np.ones(9) / 9, mode="same")
    print(f"{tag}: 拼图区最强竖边缘 x={int(np.argmax(sm))}")
