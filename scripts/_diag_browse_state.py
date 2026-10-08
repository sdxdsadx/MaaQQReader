"""run4 日志无 step.advance（verbose observe 模式），需要 diagnostics。
直接看 runner 判定状态：这个浏览广告页被判成什么状态？
若被判 AD_PLAYING 则走 advance 分支；若 UNKNOWN 则在确认阶梯里空转。"""
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from qqreader.page.feature_keys import DEFAULT_FEATURE_KEYS
from qqreader.page.recognizer import PageStateRecognizer
from qqreader.page.profiles import build_default_state_definitions

ocr = ("小", "广告", "反馈", "乔巴日用", "动车", "声大如打雷",
       "去体验9秒", "上滑或点击跳转到详情页", "去体验", "体验几秒就能领奖～")
rec = PageStateRecognizer(build_default_state_definitions(DEFAULT_FEATURE_KEYS))
from qqreader.page.observation import PageObservation
from qqreader.page.states import Orientation
obs = PageObservation(current_app=None, orientation=Orientation.PORTRAIT, ocr_texts=ocr)
d = rec.evaluate(obs)
print("state:", d.state)
# AD_PLAYING 需要 ladder required：'广告' OCR 或 skip 图标或 video 结构
# '广告'在 OCR 里 → 应命中。min_matched=2 需要再一条（app/orientation）
