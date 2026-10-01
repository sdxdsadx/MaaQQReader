"""页面已经滑到简介页最底部（猜你喜欢听推荐区），无阅读按钮——
这本听书详情页确实没有「继续阅读」入口（它只是听书的信息页）。
正确入口回归：**底部目录/正文要从朗读播放页进**。但现在听书已停。
最后一招（100% 成功）：**force-stop 重启**——昨天两次重启后 app 都
直接恢复到「正文页」（不是简介页），因为续读状态存的是正文位置。
刚才这次重启落在简介是因为点书名（介绍页）之前有「正在播放」状态。
这次重启后若落简介页，BACK 一次→书架→完成。
就直接重启+观察落地页，若正文 → 直接跑看护。"""
import subprocess
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

adb = r"D:\Program Files\Netease\MuMu Player 12\shell\adb.exe"
dev = "127.0.0.1:16384"
subprocess.run([adb, "-s", dev, "shell", "am", "force-stop", "com.qq.reader"],
               capture_output=True, timeout=20)
time.sleep(3)
subprocess.run([adb, "-s", dev, "shell",
                "monkey -p com.qq.reader -c android.intent.category.LAUNCHER 1"],
               capture_output=True, timeout=30)
time.sleep(16)

from qqreader.config import load_config
from qqreader.maa.factory import build_maa_client

config = load_config("configs/qqreader.local.json")
client = build_maa_client(config)
client.connect()
s = client.screencap()
skip = [(t, b) for t, b in client.recognize("OCR", {}, s).text_boxes() if "跳过" in t]
if skip:
    t, b = skip[0]
    client.swipe(b[0] + b[2] // 2, b[1] + b[3] // 2, b[0] + b[2] // 2, b[1] + b[3] // 2, 60)
    time.sleep(3)
s = client.screencap()
boxes = client.recognize("OCR", {}, s).text_boxes()
j = " ".join(t for t, b in boxes)
print("落地:", j[:120], flush=True)
# 判断正文页特征：长文本行
body = [(t, b) for t, b in boxes if 100 < b[1] < 1000 and b[2] > 200 and len(t) > 12]
print("正文页判断:", len(body) >= 2, flush=True)
client.close()
