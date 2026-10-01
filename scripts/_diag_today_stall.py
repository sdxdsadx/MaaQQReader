"""今日 DailyAdFlow 卡在书城页 184 observe——跟 #10 同症状但书城 OCR
变了（有'有奖'浮标）。看 recognizer 现在判什么 + runner 卡在哪一步。
关键差异：#10 修复收紧了 GAME_HALL marker，书城页现在判 UNKNOWN →
needs_recheck → 确认阶梯 → 都不确认 → _recover(state_unknown)……
但 observe 一直涨说明在循环。诊断当前屏 OCR 判定。"""
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

ocr = ("12:18", "男生", "排行榜>", "仙！", "本周强推", "今日必读", "高分必读",
       "斗罗：无双剑", "508人二刷", "尘世闲游", "无双剑山！", "生")
rec = PageStateRecognizer(build_default_state_definitions(DEFAULT_FEATURE_KEYS))
obs = PageObservation(current_app=None, orientation=Orientation.PORTRAIT, ocr_texts=ocr)
d = rec.evaluate(obs)
print("state:", d.state)
