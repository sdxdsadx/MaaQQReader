""".data 是 bytes 但 cv2.imdecode 说不是 bytes-like？——data 可能是
RGBA 裸像素（非 PNG），imdecode 解不出 → 报错文案误导。s.save() 只收路径。
改用：save 到临时文件 → 读 bytes → detect_slide。验证。"""
import sys
import tempfile
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
tmp = Path(tempfile.gettempdir()) / "cap_test.png"
s.save(str(tmp))
png = tmp.read_bytes()
print("png bytes:", len(png))
d = detect_slide(png)
print("found:", d.found, "| error:", d.error, "| track:", d.track, "| slider:", d.slider, "| dist:", d.distance)
client.close()
