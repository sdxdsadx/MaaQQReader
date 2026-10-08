"""重启后直接落在书架页（这次没有恢复到正文——好事，干净状态）。
书架上有「350章/3385章」全职法师续读行。点它进正文（上次点书名进简介，
这次点续读行 136,488 附近）。之前点「347章/3385章」行成功进了简介是因为
点的是行内章节链接——但另一次点行成功了（_open_qz347 进了简介？不，
它进的就是简介）。
看区别：点书架续读行 y=488 进的是**简介页**还是**正文**？
昨天 16:16 点 (173,452) 全职法师行 → 进了正文第35章！
(173,452) 是昨天书架的行位置。今天行在 (136,488)。行本身点击=正文。
试：点 (200,498)。"""
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
client.swipe(200, 498, 200, 498, 60)
time.sleep(4.5)
s = client.screencap()
boxes = client.recognize("OCR", {}, s).text_boxes()
body = [(t, b) for t, b in boxes if 100 < b[1] < 1000 and b[2] > 200 and len(t) > 12]
j = " ".join(t for t, b in boxes)
print("正文判断:", len(body) >= 2, "|", j[:100], flush=True)
client.close()
