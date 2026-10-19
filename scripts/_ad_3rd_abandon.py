"""还在快手广告页（BACK 无效——广告 WebView 层吃掉了 BACK）。
用 MAA 的 swipe 点击左上角返回/或顶部「观看11秒」区域外找关闭。
该广告页元素：y=53 观看11秒 / y=1120 了解详情 / y=1208 广告标识。
左上角通常有返回箭头 (30,60)。试点击；无效则试 HOME 键 + 重开 QQ阅读
（昨晚验证过 force-stop 恢复链路完整）。"""
import subprocess
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

adb = r"D:\Program Files\Netease\MuMu Player 12\shell\adb.exe"
dev = "127.0.0.1:16384"

from qqreader.config import load_config
from qqreader.maa.factory import build_maa_client

config = load_config("configs/qqreader.local.json")
client = build_maa_client(config)
client.connect()

# 尝试左上返回
client.swipe(30, 60, 30, 60, 60)
time.sleep(3)
boxes = client.recognize("OCR", {}, client.screencap()).text_boxes()
j = " ".join(t for t, b in boxes)
print("左上点击后:", j[:90], flush=True)

if "快手极速版" in j:
    # force-stop 恢复（广告放弃，礼物可能不涨）
    subprocess.run([adb, "-s", dev, "shell", "am", "force-stop", "com.qq.reader"],
                   capture_output=True, timeout=20)
    time.sleep(3)
    subprocess.run([adb, "-s", dev, "shell",
                    "monkey -p com.qq.reader -c android.intent.category.LAUNCHER 1"],
                   capture_output=True, timeout=30)
    time.sleep(14)
    s = client.screencap()
    skip = [(t, b) for t, b in client.recognize("OCR", {}, s).text_boxes() if "跳过" in t]
    if skip:
        t, b = skip[0]
        client.swipe(b[0] + b[2] // 2, b[1] + b[3] // 2, b[0] + b[2] // 2, b[1] + b[3] // 2, 60)
        time.sleep(3)
    boxes = client.recognize("OCR", {}, client.screencap()).text_boxes()
    j2 = " ".join(t for t, b in boxes)
    print("重启后:", j2[:100], flush=True)
    print("在奖励页:", ("已获赠币" in j2) or ("看小视频" in j2), flush=True)
    print("进度:", [t for t, b in boxes if "每看完1次" in t], flush=True)
client.close()
