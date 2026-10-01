"""run_task 的 observe 写到 dev\debug\maafw.log 还是 stdout？
之前 run4-8 的 observe 在 today_ad_run*.log（stdout 重定向）。
daily_all.py 把 run_task stdout 写进 daily_all_YYYYMMDD.log——但广告段只有
1 行！说明 run_task 卡在 preflight 后没输出 observe——因为 observe 打印
到 stdout 需要行缓冲，subprocess stdout=文件是块缓冲 → 进程被 timeout
kill 时缓冲丢失。这只是日志丢失，不影响判定：广告 40min timeout exit=2。

关键问题：广告任务为什么也卡？我 03:04 救场把 app 拉到「游戏中心」，
03:27 广告任务启动时页面是游戏中心——HOME 判定失败（无书架tab）→
UNKNOWN 循环？HOME→书架修复只处理 state==HOME 且无奖励入口的情况，
但游戏中心页根本判不出 HOME！修复：unknown 状态加 BACK 兜底?
先活体看当前页面。"""
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
boxes = client.recognize("OCR", {}, s).text_boxes()
print(f"OCR {len(boxes)}:")
for t, b in sorted(boxes, key=lambda x: x[1][1])[:12]:
    print(f"y={b[1]:4d} x={b[0]:4d} | {t}")
client.close()
