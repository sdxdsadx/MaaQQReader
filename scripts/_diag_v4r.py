"""直播广告已进入（倒计时 25 秒）。等待倒计时结束 + 浏览下滑（live 广告逻辑
人工预演: 等 30s → 下滑几次 → X 退出）。看能否回奖励页且进度 7/12。"""
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

# 等倒计时
time.sleep(32)
for i in range(4):
    client.swipe(360, 1000, 360, 450, 500)
    time.sleep(4)
s = client.screencap()
texts = client.recognize("OCR", {}, s).all_texts()
print("=== 浏览后页面 ===")
for t in texts[:14]:
    print(t)

# 点左上角 X (55,118)
client.swipe(55, 118, 55, 118, 80)
time.sleep(3)
s2 = client.screencap()
texts2 = client.recognize("OCR", {}, s2).all_texts()
print("=== X 后页面 ===")
for t in texts2[:16]:
    print(t)
client.close()
