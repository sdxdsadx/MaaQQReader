"""🎯 根因终于实锤（toast 提示）：
「人声朗读中无法开启自动阅读模式」
——虽然刚才暂停了听书，但**人声朗读会话还挂着**（暂停≠退出），
系统直接拒绝开启自动阅读。这就是用户说的「自动听书开着的时候无法自动阅读」。
解法：必须**彻底退出听书会话**（不只是暂停）：
方案：进 AI 朗读页 → 找退出/关闭（之前面板有「372章」、定时、倍速等，
退出朗读通常在朗读页右上角或底部「书籍简介」旁；更简单：直接 BACK 出朗读页
+ BACK 回书架，让听书会话结束）。
实验路径：呼菜单（幂等）→ 这次的「设置」里点「自动阅读」失败 toast 已证明。
先 BACK 两层退出朗读上下文 → 回书架 → 重新进书开正文 → 确认无人声朗读
toast → 再开自动阅读。"""
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
# BACK 退出正文→(朗读会话结束)→可能回书架
client.swipe(360, 640, 360, 640, 0); time.sleep(2)
client.swipe(360, 640, 360, 640, 0); time.sleep(2)
s = client.screencap()
boxes = client.recognize("OCR", {}, s).text_boxes()
for t, b in sorted(boxes, key=lambda x: x[1][1])[:14]:
    print(f"y={b[1]:4d} x={b[0]:4d} | {t}")
client.close()
