"""当前在「AI朗读-书籍信息」页（顶部 AI朗读 标题）——不是普通简介页！
这说明第342章那行在听书面板语境下点了进朗读的书籍信息。
退出路径：BACK 回书架 → 找书架上的「继续阅读」正文入口。
其实昨天进入正文的方式是书架点书名→直接进正文（续读位置）。
刚才点 (173,452)「全职法师」区域进了简介——因为那是书封面/标题区。
正确：点书架页的「第342章/3385章」续读进度行（136,488）——它通常直接跳正文。"""
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
# BACK 退出书籍信息页
client.swipe(360, 640, 360, 640, 0)
time.sleep(2)
# 回书架后点续读进度行
s = client.screencap()
progress = [(t, b) for t, b in client.recognize("OCR", {}, s).text_boxes()
            if "章/" in t and 400 < b[1] < 600]
print("续读行:", progress, flush=True)
if progress:
    t, b = progress[0]
    client.swipe(b[0] + 60, b[1] + 10, b[0] + 60, b[1] + 10, 60)
    time.sleep(3.5)
    s2 = client.screencap()
    texts = client.recognize("OCR", {}, s2).all_texts()
    print("进入:", " | ".join(texts[:6])[:130], flush=True)
client.close()
