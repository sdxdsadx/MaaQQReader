"""Screenshot 有 .save()/.data/.to_bgr。live_captcha_auto.py 内部自己
screencap 后传给 detect_slide 的方式可能直接传了对象。看 live_captcha_auto
调用点并修：传 PNG bytes（用 save 到内存或 data 属性）。"""
from pathlib import Path

src = Path(r"G:\project_X\scripts\live_captcha_auto.py").read_text(encoding="utf-8")
import re
for m in re.finditer(r"detect_slide\((.*?)\)", src):
    line_start = src.rfind("\n", 0, m.start()) + 1
    print(src[line_start:m.end()][:160])
    print("---")
# 也看它怎么拿 screenshot
for m in re.finditer(r"screencap\(\)", src):
    line_start = src.rfind("\n", 0, m.start()) + 1
    line_end = src.find("\n", m.start())
    print("CAP:", src[line_start:line_end][:150])
