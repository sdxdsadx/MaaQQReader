"""内容又变了（千手扉间…），页面在动——但可能是我 toggle 序列里
「点(355,1122)」每次都在切开关：开→关→开→关……而验证时恰逢关闭态。
真相检查：现在到底开没开？连续读三次首行（间隔 12s）看是否自动翻页。
若在翻 → 说明是开的，脚本判定逻辑有 bug（body_first_line 把右上角
"m/A" 图标 OCR 噪声当首行？过滤条件 100<y<1000 应该排掉了……但
y=108 的 "m" 在 100..1000 内！它 x=689 在右上角，是页眉图标。
修 body_first_line：排除 x>600 的右上角页眉噪声，并要求行宽>40）。"""
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

def first():
    s = client.screencap()
    boxes = client.recognize("OCR", {}, s).text_boxes()
    body = [(t, b) for t, b in boxes if 100 < b[1] < 1000 and b[0] < 600 and b[2] > 40]
    body.sort(key=lambda x: x[1][1])
    return body[0][0] if body else "(空)"

a = first(); time.sleep(12); b = first(); time.sleep(12); c = first()
print("1:", a[:24])
print("2:", b[:24])
print("3:", c[:24])
print("在自动翻页:", (a != b) or (b != c))
client.close()
