"""detect_slide 期待 PNG bytes；Screenshot.data 大概是裸 BGR/RGBA 数组
或 memoryview——imdecode 失败。快速实验确认 .data 类型与 png bytes 获取方式
（save 到 BytesIO）。"""
import io
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from qqreader.config import load_config
from qqreader.maa.factory import build_maa_client
from qqreader.captcha.slide import detect_slide

config = load_config("configs/qqreader.local.json")
client = build_maa_client(config)
client.connect()
s = client.screencap()
print("data type:", type(s.data))
buf = io.BytesIO()
s.save(buf)
png = buf.getvalue()
print("png bytes:", len(png))
d = detect_slide(png)
print("detect_slide(png):", d.found, d.error, d.track, d.slider, d.distance)
client.close()
