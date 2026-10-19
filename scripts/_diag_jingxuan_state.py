"""BACK 生效了：退出游戏中心 tab 到「精选大作/阅游戏」外层页（4:26→4:31
一直在 BACK：'精选大作'页也是游戏域页面，判什么状态？可能也是 GAME_CENTER
或另一个 state。BACK 链在逐层退出——继续观察是否最终到 HOME。若这个
'精选大作'页也是独立 state 则又要加。先看判定。"""
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from qqreader.page.feature_keys import DEFAULT_FEATURE_KEYS
from qqreader.page.recognizer import PageStateRecognizer
from qqreader.page.profiles import build_default_state_definitions

ocr = ("终焉九尾", "精选大作", "首页", "新游", "仙途伏魔",
       "乐享元游青云伏之伏魔", "西行纪正版联动", "燃战西行", "阅游戏")
d = PageStateRecognizer(build_default_state_definitions(DEFAULT_FEATURE_KEYS)).evaluate(
    __import__("qqreader.page.observation", fromlist=["PageObservation"]).PageObservation(
        current_app=None,
        orientation=__import__("qqreader.page.states", fromlist=["Orientation"]).Orientation.PORTRAIT,
        ocr_texts=ocr))
print("state:", d.state)
