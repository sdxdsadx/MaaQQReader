"""活体诊断: 截当前屏 → detect_slide → OCR, 打印验证码在场状态。"""
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from qqreader.captcha.slide import detect_slide
from qqreader.config import load_config
from qqreader.maa.factory import build_maa_client

OUT = _ROOT / "runtime" / "screenshots" / "19700105"

config = load_config("configs/qqreader.local.json")
client = build_maa_client(config)
client.connect()
s = client.screencap()
data = s.data if hasattr(s, "data") else s
p = OUT / "autocap_r0.png"
p.write_bytes(data)
d = detect_slide(data)
print("detect:", "FOUND" if d.found else f"FAIL({d.error})")
print(f"  track={d.track} slider={d.slider} center={d.slider_center} dist={d.distance}")

ocr = client.recognize("OCR", {}, s)
dd = ocr.detail if isinstance(ocr.detail, dict) else {}
items = dd.get("all") or []
texts = [str(i.get("text", "")) for i in items if isinstance(i, dict)]
print("OCR boxes:", len(texts))
for t in texts:
    print("  |", t[:60])
joined = " ".join(texts)
print("CAPTCHA_ON:", ("安全验证" in joined) or ("滑块" in joined) or ("拖动" in joined))
print("REWARD_PAGE:", any(k in joined for k in ("今日已获赠币", "看小视频领好礼", "玩游戏领赠币")))
client.close()
