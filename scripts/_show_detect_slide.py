"""live_captcha_auto.py 已经写了 data = s.data if hasattr(s,'data') else s
——那 data 是什么类型？可能 .data 返回 numpy/bytes 但 detect_slide 期待
PNG bytes？看 detect_slide 签名与内部解码方式。"""
from pathlib import Path

root = Path(r"G:\project_X\qqreader\captcha\slide.py")
src = root.read_text(encoding="utf-8")
i = src.find("def detect_slide")
print(src[i:i+900])
