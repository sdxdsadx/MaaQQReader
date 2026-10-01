"""抓到真凶：detect_slide 收到 Screenshot 对象但当 bytes 用——
「截图解码失败: a bytes-like object is required, not 'Screenshot'」。
之前成功是因为调用路径不同（旧 run_task 链里传的是 PNG bytes）。
验证码明明在（安全验证/拖动下方滑块 OCR 可见）。
修：看 Screenshot 对象的接口（.png_bytes/.save/to_png）——查 maa factory
返回类型定义。"""
import sys
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
print(type(s))
print([m for m in dir(s) if not m.startswith("_")])
client.close()
