"""⚠ 重大异常：今日已获赠币只有 **10**！昨天明明 208！
且「已连」「签到成功」「恭喜获得以下奖励 获得5赠币」——
**这是新的一天/新账号状态**：连续签到 22 天记录消失，奖励从 5 赠币开始。
两种可能：
①QQ阅读每日 0 点重置（现在是凌晨 5:22，新的一天开始——昨天的 208 是
  09-14 的，今日 09-15 重新计数，正常！）——签到动画正在播放。
②账号被重置（不太可能）。
判断：正常跨日重置。今天（09-15）的签到+奖励重新开始。
这也意味着：300 分钟阅读的时长档位是「今日」口径，今天 0 点后新算——
昨晚 146 分钟时长是 09-14 的，不带入今天！但今天凌晨的滑动阅读
00:29-05:12 的时间会计入今天（146 分钟可能就是今天的！）。
冷静核实：等签到动画结束 → OCR 完整奖励页 → 看「再读N分钟」状态。"""
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from qqreader.config import load_config
from qqreader.maa.factory import build_maa_client

config = load_config("configs/qqreader.local.json")
client = build_maa_client(config)
client.connect()
time.sleep(6)
client.swipe(360, 1050, 360, 500, 600)
time.sleep(2)
s = client.screencap()
boxes = client.recognize("OCR", {}, s).text_boxes()
for t, b in sorted(boxes, key=lambda x: x[1][1]):
    if any(k in t for k in ("再读", "已听", "领取", "分钟", "已获赠币")):
        print(f"y={b[1]:4d} x={b[0]:4d} w={b[2]:3d} | {t}", flush=True)
client.close()
