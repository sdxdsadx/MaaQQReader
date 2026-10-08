"""还是 toast「人声朗读中无法开启自动阅读模式」——朗读会话仍挂着。
浮窗已消失但会话没死。需要找到听书会话的真正退出开关：
回 AI 朗读页（浮窗没了怎么进？）→ 奖励页听书卡入口「去听书」？
更直接：书架页顶部有「听书」tab 或重新点开书 → 底部「听」按钮 →
AI 朗读页 → 面板里找退出。
观察之前朗读页 OCR：底部有「书籍简介」，无明确退出。AI 朗读页右上角
「C」(x=561,y=68) 或 (619,958)「三」？「查看原文」只是回正文。
试：目录图标/底部「书籍简介」上方区域通常有关闭键。
另一个思路：**这是浮窗模式**——之前浮窗「听」点开是展开面板，浮窗本体
可长按/双击关闭？用户说"左下角有自动阅读的浮游框，点那个叉"——
用户说的是**自动阅读浮窗**（开自动阅读后出现的浮窗），不是听书浮窗！
重新理解用户指示：
- 进阅读界面时左下角有「自动阅读」浮窗（上次自动阅读会话的遗留）
- 点它的 X 关掉 → 再开自动阅读
但 toast 说的是人声朗读——真正挡路的是朗读会话。两件事都要处理：
1) 听书会话：彻底退出。入口：重新点「去听书」或在书架/书籍详情页停掉
2) 自动阅读遗留浮窗：点 X
先回书架页看听书状态。"""
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from qqreader.config import load_config
from qqreader.maa.factory import build_maa_client

config = load_config("configs/qqreader.local.json")
client = build_maa_client(config)
client.connect()
# BACK 出正文页（前面 BACK 被菜单吃了，这次菜单已收）
client.swipe(360, 640, 360, 640, 0); time.sleep(2)
client.swipe(360, 640, 360, 640, 0); time.sleep(2)
s = client.screencap()
boxes = client.recognize("OCR", {}, s).text_boxes()
for t, b in sorted(boxes, key=lambda x: x[1][1])[:16]:
    print(f"y={b[1]:4d} x={b[0]:4d} | {t}")
client.close()
