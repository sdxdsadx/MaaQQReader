"""验证: 书城页 OCR 里「男生频道」其实属于主页——底部有「书城」tab 吗?
回看 v4 r1 observe 1 的完整 OCR（12 条截断了，可能后续含「书城」）。
dump r1 全部 observe 的完整 ocr list，找含「书城/书架/我的」的行。"""
from pathlib import Path
import ast

p = Path(r"G:\project_X\runtime\logs\supervise_r1.log")
rows = p.read_text(encoding="utf-8", errors="replace").splitlines()
seen = set()
for r in rows:
    if not r.startswith("[observe"):
        continue
    i = r.find("ocr=[")
    if i < 0:
        continue
    try:
        ocr = ast.literal_eval(r[i + 4:].strip())
    except Exception:
        continue
    for t in ocr:
        if any(k in t for k in ("书城", "书架", "我的", "会员", "男生 女生")):
            key = t
            if key not in seen:
                seen.add(key)
                print("发现:", t)
    if len(seen) > 10:
        break
print("共发现特征:", seen)
