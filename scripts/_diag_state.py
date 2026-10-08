"""r1 卡死页状态判定 + 各候选分数。已知结论: state=AD_PLAYING confirmed=True。
问题: 「跳转详情页或第三方应用」「了解详情」属于 offer 广告（offer_texts 处理链），
advance 里 offer_close_action=press_back。为何 800 observe 不动? 看决策诊断。"""
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from qqreader.page.feature_keys import DEFAULT_FEATURE_KEYS
from qqreader.page.recognizer import PageStateRecognizer
from qqreader.page.profiles import build_default_state_definitions
from qqreader.page.observation import PageObservation
from qqreader.page.states import Orientation

ocr = (
    "X", "观看30秒，可获得奖励", "生了生了生了！", "在？上号！在超自然行动组摸一把！",
    "跳转详情页或第三方应用", "超自然新手小黄", "了解详情", "广告",
)
rec = PageStateRecognizer(build_default_state_definitions(DEFAULT_FEATURE_KEYS))
obs = PageObservation(current_app=None, orientation=Orientation.PORTRAIT, ocr_texts=ocr)
d = rec.evaluate(obs)
print("state:", d.state)
for c in d.candidates()[:5] if callable(getattr(d, "candidates", None)) else []:
    print("  cand:", c.state, round(c.score, 3), "missing:", [f.spec.key for f in c.missing_required])
