"""这是完整 AI 朗读页（不是正文页）！刚才点浮窗跳进了朗读页。
页面元素：暂停键 II (334,834)、目录、AI朗读标题。
用户说「自动听书开着时无法自动阅读」——需要先**关掉听书**：
①在朗读页暂停播放（点 II → 变播放键）——但浮窗可能还在
②退出朗读页回正文页（查看原文 y=1102 或 BACK）
③确认正文页左下/右下浮窗已无 → 开自动阅读
计划：点暂停(358,846) → 点「查看原文」(494,1112) 回正文 → OCR 验证
浮窗是否还在 → 若在找 X 关闭。"""
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

client.swipe(358, 846, 358, 846, 60)   # 暂停听书
time.sleep(1.5)
client.swipe(494, 1112, 494, 1112, 60)  # 查看原文 → 回正文
time.sleep(2.5)
s = client.screencap()
boxes = client.recognize("OCR", {}, s).text_boxes()
print("回正文后底部区域:", flush=True)
for t, b in sorted(boxes, key=lambda x: x[1][1]):
    if b[1] > 950:
        print(f"y={b[1]:4d} x={b[0]:4d} | {t}", flush=True)
client.close()
