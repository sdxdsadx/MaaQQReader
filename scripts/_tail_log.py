"""读 reading_flow_run.log（*> 编码不定，容错读取）最后 N 行。"""
import sys
from pathlib import Path

p = Path(r"G:\project_X\runtime\logs\reading_flow_run.log")
raw = p.read_bytes()
for enc in ("utf-8", "gbk"):
    try:
        text = raw.decode(enc)
        break
    except UnicodeDecodeError:
        continue
else:
    text = raw.decode("utf-8", errors="replace")
rows = [r for r in text.splitlines() if r.strip()]
print("总行数:", len(rows))
for r in rows[-int(sys.argv[1]) if len(sys.argv) > 1 else -8:]:
    print(r[:150])
