"""矛盾：完整 63 条 OCR → HOME；runner 观测却 UNKNOWN 循环。
差异只能在 runner 拿到的 OCR 与我直接拿的不同——MAA OCR 的 batch 缓存？
看 run_task 用的 MaaPageObserver（同一 client.recognize('OCR',{},shot)）。
可疑点：runner 的 DeviceScreencapGuard / LoggingObserver 包装会不会截断
ocr_texts？查 MaaPageObserver.observe 返回的 ocr_texts 来源 all_texts()——
之前看过，完整。那 runner 为什么 needs_recheck？
—— 等等，看 recognizer.evaluate 对「有奖」的处理：书城页顶部有「有奖」浮标
（observe 182 有'有奖'），GAME_HALL marker 收紧后…先直接用 runner 同款链路
（client + observer + recognizer）跑一次完整判定看 state。"""
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
    DEFAULT_FEATURE_KEYS,
    rois={"game_ocr_online_play": (0, 800, 720, 1280)},
)
observer = MaaPageObserver(client, catalog, target_package=DEFAULT_FEATURE_KEYS.qq_reader_package)

class _Ctx:
    pass

ctx = _Ctx()
obs = observer.observe(ctx)
print("observer ocr_texts 数:", len(obs.ocr_texts))
print("底部含书架:", any("书架" in t for t in obs.ocr_texts))
rec = PageStateRecognizer(build_default_state_definitions(DEFAULT_FEATURE_KEYS))
d = rec.evaluate(obs)
print("runner链路 state:", d.state)
client.close()
