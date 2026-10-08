"""K: ASCII 图解读——y778-810 有清晰结构:
  y786: @@@@@@@@@@@#*++++++++++*#@@@...  → x≈168-290 有个「+」暗块（宽~118px!）
  y794: @@@@@@@@@%+--------------+%@@ → 同一暗块更暗（--------------）
  y802: @@@@%%%%%+-----=-==-=-----+%% → 轨道内
  这就是**滑块按钮**（x≈168..286, y≈786..810）——在轨道里的按钮，中心≈227!
  
  而检测器报的蓝色按钮 (109,789,118,59) 中心 (168,818)?? ASCII y810 行
  '###------*-+=-*------###' → 按钮 x 范围其实 155..295。检测器 box 左缘 109
  可能含蓝色高亮部分。按钮真实中心 ≈ (168+286)/2 = 227。

  拼图缺口: y690..778 的图块区，找「方块洞」——注意 y690-706 行 x≈390-480
  有连续 ########（暗块），x≈500-620 是 :::::（更暗均匀）——缺口可能在
  x≈500-620!（最暗列 489-501 也在附近）
  
  → 缺口中心≈560, 滑块头需从 227 移到 560 → 位移 333px（1:1!）
  
结论: 按钮真实中心不是 168 而是 227（蓝色 mask 左缘 109 是把按钮左侧
半透明蓝描边也算进去了），导致 raw=distance 全错!
修正: 按钮中心 = 轨道内暗块中心（y786..810 的暗区），而非蓝色轮廓中心。
"""
from pathlib import Path

import cv2
import numpy as np

ACC = Path(r"G:\project_X\runtime\screenshots\19700104")
img = cv2.imdecode(np.fromfile(str(ACC / "probeF_end.png"), dtype=np.uint8), cv2.IMREAD_COLOR)
g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

# 按钮精确框: y 786..810, 找暗区（值<150）的 x 范围
band = g[786:810, :]
mask = band < 150
cols = mask.sum(axis=0)
xs = np.where(cols >= 20)[0]  # 大部分行都暗的列
print("按钮暗区列范围:", xs.min() if xs.size else None, "..", xs.max() if xs.size else None)
if xs.size:
    center_btn = (int(xs.min()) + int(xs.max())) // 2
    width = int(xs.max() - xs.min())
    print(f"按钮: x {xs.min()}..{xs.max()} 宽{width} 中心={center_btn}")

# 缺口: y 690..775 图块区找暗色矩形（与周围背景差异大）
band2 = g[690:775, 300:655]
m2 = band2 < 140
cols2 = m2.sum(axis=0)
# 连续暗列段
segs = []
run = 0
start = 0
for x, v in enumerate(cols2):
    if v > 40:
        if run == 0:
            start = x
        run += 1
    else:
        if run > 40:
            segs.append((300 + start, run))
        run = 0
if run > 40:
    segs.append((300 + start, run))
print("图块区暗色连续段（候选缺口）:", [(s, w, 300 + s + w // 2) for s, w in segs])
