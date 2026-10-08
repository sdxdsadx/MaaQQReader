"""今日进度 6/12！继续下滑找「立即观看」按钮并点击——验证广告还能进。
若能进广告 → runner 修复方案: HOME 动作改为「切书架 tab + 点 再读N分钟领赠币」？
不——reward 入口在书架页 home_ocr_reward_entry 正则已覆盖（再读10分钟领20赠币）。
问题只是 runner 启动时 app 停在书城 tab（男生频道），home_ocr_reward_entry 定位不到。
修复: HOME 动作失败时先滑到书架 tab（点 y=1250 x=89）再定位。
先人工验证: 点立即观看能进广告。"""
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
s = client.screencap()
ocr = client.recognize("OCR", {}, s)
boxes = ocr.text_boxes()
btn = None
for t, b in boxes:
    if "立即观看" in t:
        btn = b
        break
print("立即观看 box:", btn)
if btn:
    x = btn[0] + btn[2] // 2
    y = btn[1] + btn[3] // 2
    print(f"点击 ({x},{y})")
    client.swipe(x, y, x, y, 80)
    time.sleep(6)
    s2 = client.screencap()
    ocr2 = client.recognize("OCR", {}, s2)
    texts2 = ocr2.all_texts()
    joined = " ".join(texts2[:14])
    print("点击后页面:", joined[:200])
client.close()
