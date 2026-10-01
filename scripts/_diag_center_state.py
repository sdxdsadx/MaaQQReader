"""observe 28-57 仍在游戏中心页——UNKNOWN BACK 兜底没生效？！
原因排查：patch 加在 advance() 开头 state 计算之后，但条件是 state is None。
先确认：游戏中心页 recognizer 判定是什么？可能不是 None 而是
GAME_ENTRY（OCR 有'在线玩'）→ 命中 GAME_ENTRY 分支（有 tap 在线挂机？）
而不进我的兜底。用 diag 链路实测当前页判定。"""
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from qqreader.config import load_config
from qqreader.maa.factory import build_maa_client
from qqreader.maa.observer import MaaPageObserver
from qqreader.maa.catalog import FeatureCatalog
from qqreader.page.feature_keys import DEFAULT_FEATURE_KEYS
from qqreader.page.recognizer import PageStateRecognizer
from qqreader.page.profiles import build_default_state_definitions

config = load_config("configs/qqreader.local.json")
client = build_maa_client(config)
client.connect()
catalog = FeatureCatalog.from_feature_keys(
    DEFAULT_FEATURE_KEYS, rois={"game_ocr_online_play": (0, 800, 720, 1280)})
observer = MaaPageObserver(client, catalog, target_package=DEFAULT_FEATURE_KEYS.qq_reader_package)

class _Ctx: pass
ctx = _Ctx()
obs = observer.observe(ctx)
print("OCR 数:", len(obs.ocr_texts))
d = PageStateRecognizer(build_default_state_definitions(DEFAULT_FEATURE_KEYS)).evaluate(obs)
print("state:", d.state)
print("matched:", getattr(d, "matched_features", None))
client.close()
