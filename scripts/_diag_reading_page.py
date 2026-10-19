"""真相大白: 不是节点缺失！是 **任务超时**：
- DirectReadingFlow 的 next 三节点（书名 OCR/封面模板/第一本）全部 Recognition.Failed
- PipelineTask 报「Task timeout [duration=20889ms]」→ pretask 超时（默认 20s）
- 因为三个候选都没识别到 → 20 秒后超时失败 → run_next bad next → invalid node id

根因：启动 QQ阅读后停在「书城页/男生频道」——奖励页入口 OCR「本周阅读时长|再读
N分钟领赠币」在书架页才有，书城页没有 → 三个 Terminal 全不识别。

修复方向（最小改动，两选一）：
A. run_maa_ad.py 传入 pipeline_override，把 DirectReadingFlow.post_delay 提高
   （没用——问题在识别，不在等待）
B. **正确做法**：在 DirectReadingFlow 的 next 前加一个「确保在书架页」节点：
   先按底部「书架」tab（OCR「书架」y=1250 或固定坐标 (89,1263)），再找书。
   或直接把 recognition 前置节点 ReadingGotoShelf 加进 json。

先验证当前 app 停在什么页——刚才 StartApp 已执行（阅读 app 已在前台）。
用 _diag_v4e 抓当前页 OCR 确认在哪个 tab。"""
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
s = client.screencap()
boxes = client.recognize("OCR", {}, s).text_boxes()
print("=== 当前页 OCR（前 14）===")
for t, b in sorted(boxes, key=lambda x: x[1][1])[:14]:
    print(f"y={b[1]:4d} x={b[0]:4d} | {t}")
client.close()
