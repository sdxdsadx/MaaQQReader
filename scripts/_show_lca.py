"""看 live_captcha_auto.py 里 screencap 后 data= 那几行。"""
from pathlib import Path

src = Path(r"G:\project_X\scripts\live_captcha_auto.py").read_text(encoding="utf-8")
i = src.find("s = client.screencap()")
print(src[i-200:i+300])
