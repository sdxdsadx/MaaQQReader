"""根因确认: 书城页（男生频道）没有「本周阅读时长/再读N分钟领赠币」——
那是书架页的奖励入口。书城页正确的入口是顶部 tab 旁的什么？
活体 OCR（_diag_v4e）：男生(y=48) 女生(50) 出版(50) 会员(52/53) 听书(52)
免费(52) 漫剧(53)——这些是顶部频道 tab。「有奖」在 observe 1 出现过！
r1 observe 1: ocr=['6:27', '男生', '排行榜>', '本周强推', '今日必读', '高分必读',
'斗罗：先天半', '级，但是唯...', '武魂彩虹龙', '天才对决', '麟月成情敌？', '送你31天会员']
——[:12] 截断, 原始应有更多。

回到 QQ阅读 app 实际导航: 书城页顶部有「福利中心」入口? 我们的记忆:
「奖励页入口=看书领币的浮标」。旧 pipeline 的奖励入口是「有奖」浮标按钮！
observe 1 里有「有奖」——那是浮动奖励入口！

修复: home_ocr_reward_entry 正则加「有奖|福利|领赠币」→ 点击「有奖」进奖励页。
验证: 用活体 OCR 找「有奖」的 box 坐标确认可点击。
"""
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from qqreader.config import load_config
from qqreader.maa.factory import build_maa_client

config = load_config("configs/qqreader.local.json")
client = build_maa_client(config)
client.connect()
s = client.screencap()
ocr = client.recognize("OCR", {}, s)
boxes = ocr.text_boxes()
print("=== 含 有奖/福利/奖励/赠币 的文本及坐标 ===")
for t, b in boxes:
    if any(k in t for k in ("有奖", "福利", "奖励", "赠币", "书城", "书架")):
        print(f"box={b} | {t}")
client.close()
