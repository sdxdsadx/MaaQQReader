"""诊断: r1 卡在「男生频道/书城页」118 observe 不动——根本没到奖励页。
看 runner 状态判定与动作: 这页 OCR 有「男生」「排行榜」没有「书架」，
之前 observe 1-5 有「安装新版本」弹窗——可能是这个弹窗挡住后续点击？
另外看这页被判定为什么状态（HOME?），tap 什么特征。"""
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
    "6:09", "男生", "排行榜>", "本周强推", "今日必读", "高分必读",
    "斗罗：先天半", "级，但是唯...", "武魂彩虹龙", "天才对决",
    "麟月成情敌？", "送你31天会员",
)
rec = PageStateRecognizer(build_default_state_definitions(DEFAULT_FEATURE_KEYS))
obs = PageObservation(current_app=None, orientation=Orientation.PORTRAIT, ocr_texts=ocr)
d = rec.evaluate(obs)
print("state:", d.state)

# 带弹窗版本
ocr2 = ("5:53", "男生 女生 出版 会员", "安装新版本", "有奖", "排行榜>", "高分必读")
obs2 = PageObservation(current_app=None, orientation=Orientation.PORTRAIT, ocr_texts=ocr2)
d2 = rec.evaluate(obs2)
print("with-popup state:", d2.state)
