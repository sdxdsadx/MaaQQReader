"""决定性: 书城页全屏 OCR 是否含「书城/书架」——直接用 MAA client 跑一遍并
打印 all_texts 长度与内容。刚才 _diag_v4e 用的是同一 client（活体）确实看到
y=1250 书架/书城。但 runner 的 OCR 是同样的调用。

那 r1 卡死时（6:27-6:33）页面底部导航也许被广告浮层盖住？或者那次会话
底部导航 OCR 没出来。现在再跑一次 runner 会话里观察 ocr 是否完整。
先直接验证当前帧: all_texts 里有没有「书城」「书架」。"""
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from qqreader.config import load_config
from qqreader.maa.factory import build_maa_client
from qqreader.page.feature_keys import DEFAULT_FEATURE_KEYS
from qqreader.page.recognizer import PageStateRecognizer
from qqreader.page.profiles import build_default_state_definitions
from qqreader.page.observation import PageObservation
from qqreader.page.states import Orientation

config = load_config("configs/qqreader.local.json")
client = build_maa_client(config)
client.connect()
s = client.screencap()
ocr = client.recognize("OCR", {}, s)
texts = ocr.all_texts()
print("all_texts 条数:", len(texts))
print("含书城:", any("书城" in t for t in texts), " 含书架:", any("书架" in t for t in texts))

rec = PageStateRecognizer(build_default_state_definitions(DEFAULT_FEATURE_KEYS))
obs = PageObservation(current_app=None, orientation=Orientation.PORTRAIT, ocr_texts=texts)
d = rec.evaluate(obs)
print("state:", d.state)
client.close()
