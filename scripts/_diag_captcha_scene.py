"""场景确认：滑块验证码弹出（安全验证/拖动下方滑块完成拼图）。
跑 detect_slide 看检测状态，再用 live_captcha_auto.py 专解此问题。"""
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
from qqreader.captcha.slide import detect_slide

ocr = ("1:40", "今日已获赠币140", "看小视频领好礼", "立即观看", "安全验证",
       "拖动下方滑块完成拼图", "ıI", "C", "AI生成背景")
rec = PageStateRecognizer(build_default_state_definitions(DEFAULT_FEATURE_KEYS))
obs = PageObservation(current_app=None, orientation=Orientation.PORTRAIT, ocr_texts=ocr)
print("state:", rec.evaluate(obs).state)
