"""还是简介页。回看昨天成功记录：昨天 auto_read 前置导航是
_restart_for_autoread.py + 正文已在（BACK 后停正文）——它没从书架点书！
昨天 16:16 成功链：app 恰好停在正文页（重启后恢复到正文）。
刚才多次重启也恢复到正文（第34章/第39章）——但后来变成恢复到简介页/听书页
是因为「正在播放」状态被记录。
正解：重启后如果落在简介/朗读页，直接点「查看原文」或第N章行进正文。
当前就在简介页——先下滑到底部其实按钮在**最底部**（昨天下滑5次都没到），
用大滑动力度 2 次到页底找按钮。"""
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
for i in range(4):
    client.swipe(360, 1200, 360, 300, 250)  # 快速大滑
    time.sleep(1.2)
    s = client.screencap()
    boxes = client.recognize("OCR", {}, s).text_boxes()
    btn = [(t, b) for t, b in boxes
           if any(k in t for k in ("继续阅读", "开始阅读", "免费阅读", "阅读全文", "第348章"))]
    if btn:
        t, b = btn[0]
        print(f"按钮: {t}", flush=True)
        client.swipe(b[0] + b[2] // 2, b[1] + b[3] // 2, b[0] + b[2] // 2, b[1] + b[3] // 2, 60)
        time.sleep(4)
        s2 = client.screencap()
        texts = client.recognize("OCR", {}, s2).all_texts()
        print("进入:", " | ".join(texts[:5])[:110], flush=True)
        break
    j = " ".join(t for t, b in boxes)
    print(f"滑{i+1}: {j[:60]}", flush=True)
client.close()
