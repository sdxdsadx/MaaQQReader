"""书架页正常、无弹窗遮挡。「时长兑赠币，立即领取>」(56,194,w219) 在
y=194——之前点 (540,204) 超出按钮宽度（w219 → x 56..275）！
行尾 x=540 是「签到领赠币」(537,168) 的位置——点错了行！
正确：点「时长兑赠币」行的中后段 (200,207) 或箭头处 (260,207)。
之前 (165,204) 应该有效……可能点了但页面是滚动状态没刷新？
这次精确点按钮文字中心 (165,207)，等待 4s（页面跳转慢）。"""
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
    return None

client.swipe(165, 207, 165, 207, 80)
time.sleep(4)
result = coins()
print("点击后:", result, flush=True)

if not result:
    # 可能弹了活动弹窗（中秋找玉兔），OCR 全页确认
    s = client.screencap()
    boxes = client.recognize("OCR", {}, s).text_boxes()
    for t, b in sorted(boxes, key=lambda x: x[1][1])[:12]:
        print(f"y={b[1]:4d} x={b[0]:4d} | {t}", flush=True)
client.close()
