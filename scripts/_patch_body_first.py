"""正文页内容又前进了（不同段落），且右上角"111"噪声仍会被 body_first_line
读成首行（111 x=693 w=18——已被 x<600 过滤掉，但 11:24 log 显示首行=111，
说明截图时序里过滤没生效？——11:24 的两次运行是旧版过滤（b[0]<600 是
_probe 里加的，auto_read 的 body_first_line 还没有这个过滤！）
修 body_first_line：加 x<600 + w>40 过滤（跟 _probe 一致）。"""
from pathlib import Path

p = Path(r"G:\project_X\scripts\auto_read_30min.py")
src = p.read_text(encoding="utf-8")
old = """def body_first_line():
    boxes = [(t, b) for t, b in ocr_all() if 100 < b[1] < 1000]"""
new = """def body_first_line():
    boxes = [
        (t, b) for t, b in ocr_all()
        if 100 < b[1] < 1000 and b[0] < 600 and b[2] > 40
    ]"""
assert old in src
src = src.replace(old, new)
p.write_text(src, encoding="utf-8")
print("body_first_line 过滤已同步")
