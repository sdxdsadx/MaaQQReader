"""v4 r1 深诊断: 书城页 126 observe——UNKNOWN 状态下 runner 为什么不动?
看 runner 对 UNKNOWN/未确认状态的决策路径（confirm 器？reobserve 循环？）
同时 dump 完整决策日志：打开 run_task 的 verbose 决策输出? 先查 runner 逻辑。"""
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# 1) 书城页现在的判定
from qqreader.page.feature_keys import DEFAULT_FEATURE_KEYS
from qqreader.page.recognizer import PageStateRecognizer
from qqreader.page.profiles import build_default_state_definitions
from qqreader.page.observation import PageObservation
from qqreader.page.states import Orientation

ocr = ("6:33", "男生", "排行榜>", "本周强推", "今日必读", "高分必读",
       "斗罗：先天半", "级，但是唯...", "武魂彩虹龙", "天才对决",
       "麟月成情敌？", "送你31天会员")
rec = PageStateRecognizer(build_default_state_definitions(DEFAULT_FEATURE_KEYS))
obs = PageObservation(current_app=None, orientation=Orientation.PORTRAIT, ocr_texts=ocr)
d = rec.evaluate(obs)
print("state:", d.state)

# 2) runner 对非 start 状态怎么处理——读 runner 主循环
runner = (_ROOT / "qqreader" / "runner" / "runner.py").read_text(encoding="utf-8")
import re
# 找 UNKNOWN / fallback / confirm 相关段
for m in re.finditer(r"(?:UNKNOWN|unknown|not_present|temporary_mismatch|reobserve)", runner):
    s = max(0, m.start() - 200)
    seg = runner[s:m.end() + 300]
    print("----", seg[-420:].replace("\n", " ")[:400])
    break
