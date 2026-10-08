"""决定性发现: 活体书城页底部导航 OCR 有 y=1250「书架」「书城」「发现」「我的」！
但 runner 观测里 OCR 只有 12 条截断（observe 行只打前 12 条）——
「书架」在 y=1250 排很后，被截断掉 → HOME 的 required ladder 匹配
用完整 ocr_texts 应该能命中「书架」……但 r1 里没确认成功？

疑点: observe 打印截断[:12] 只是日志显示；recognize 用完整列表。
那书城页应判 HOME。但书城页 OCR 无「书城」二字在 r1 观测?——不对，
活体 OCR 明明有 y=1253「书城」。

再想: _diag_v4.py 用的 12 条（截断）判 UNKNOWN；完整列表会不会判 HOME？
立即验证: 用刚才活体 OCR 完整列表喂 recognizer。
"""
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

ocr_full = (
    "6:38", "男生", "排行榜>", "本周强推", "今日必读", "高分必读",
    "斗罗：先天半", "级，但是唯...", "武魂彩虹龙", "天才对决",
    "麟月成情敌？", "但是唯心剑修", "先天半级", "购书低至4折",
    "书架", "赢宝石大奖", "女生", "斗罗", "会员", "出版",
    "斗罗：麒麟双", "生，玄子赖..", "斗罗大陆",
    "斗罗：武魂彩虹龙，麟月成情敌？", "书城", "双生", "漫剧",
    "开局流", "宝可梦：开局", "神兽男，鬼..", "书库>", "100万+好书",
    "发现", "听书", "免费", "我的", "更多>", "内",
)
rec = PageStateRecognizer(build_default_state_definitions(DEFAULT_FEATURE_KEYS))
obs = PageObservation(current_app=None, orientation=Orientation.PORTRAIT, ocr_texts=ocr_full)
d = rec.evaluate(obs)
print("完整 OCR state:", d.state)

# 只取 r1 日志那种（observe 行截断 12 条）——runner 实际用的 observation 是完整的
# 所以问题可能不在这。但 r1 里 runner 一直 needs_recheck？
# 关键差异: runner 的 observation 来自 MAA OCR 同一帧——内容应相同。
# 看 r1 observe 行到底打了什么[:12]；以及 match 失败的 feature 报告（page.unknown 的 failed_features 在 diagnostics 里，结束时才打印）。
