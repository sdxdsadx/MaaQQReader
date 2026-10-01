"""验证「跳过」可点击：点顶部行 (444+264-20, 18+12)≈(688,30) —— 跳过文字位置。
若点击后页面变化（回奖励页/出现领奖弹窗），说明可行；再查为何 tap_feature
没命中——可能是 locator 的 skip_key ROI 不含 y=18 顶部行。查 FeatureCatalog
中 ad_skip 的默认 ROI。"""
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from qqreader.config import load_config
from qqreader.maa.factory import build_maa_client

config = load_config("configs/qqreader.local.json")
client = build_maa_client(config)
client.connect()
client.swipe(688, 30, 688, 30, 60)
time.sleep(3)
s = client.screencap()
texts = client.recognize("OCR", {}, s).all_texts()
print("点击跳过后页面:", " ".join(texts[:12])[:180])
client.close()

print("\n--- ad_skip catalog ROI ---")
from qqreader.maa.catalog import FeatureCatalog
from qqreader.page.feature_keys import DEFAULT_FEATURE_KEYS as K
cat = FeatureCatalog.from_feature_keys(K)
a = cat.assets.get(K.ad_skip)
print("ad_skip asset:", a)
