"""页面细节终于看全了：
- 「签到成功」动画浮层还挂着（恭喜获得以下奖励/我知道了 y=740）——
  浮层挡住下面的卡片点击！之前 5 次领取点击都打在浮层上！
- y=1053 有两个 +20、y=1085 X、y=1148 10分钟/30分钟、y=1176 两个领取——
  这是阅读时长档位卡（被浮层部分遮挡）。
处理：点「我知道了」关闭签到浮层 → 再点两个档位领取。"""
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

def coins():
    s = client.screencap()
    for t, b in client.recognize("OCR", {}, s).text_boxes():
        if "今日已获赠币" in t:
            return t
    return "?"

# 关闭签到浮层
client.swipe(352, 752, 352, 752, 60)
time.sleep(2.5)
print("浮层关闭后:", coins(), flush=True)

# 领取 10 分钟档 (197+18, 1176+18)
client.swipe(215, 1194, 215, 1194, 60)
time.sleep(2.5)
print("10分钟档:", coins(), flush=True)

# 领取 30 分钟档 (483+18, 1176+18)
client.swipe(501, 1194, 501, 1194, 60)
time.sleep(2.5)
print("30分钟档:", coins(), flush=True)
client.close()
