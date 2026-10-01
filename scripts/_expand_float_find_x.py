"""BACK x2 后仍在正文页（BACK 被菜单吃掉了）。换路径：
用底部「目录」旁路径不行——直接用「查看原文」不可用（没在朗读页）。
正解：朗读会话的彻底退出入口 = AI 朗读页里。进朗读页：呼菜单 → 点「设置」
面板之外，之前发现浮窗「听」在正文页右下 (620,1085)——点它进朗读页，
朗读页里找「关闭/退出」控制。刚才在朗读页见到 II 暂停、定时/倍速/下载。
退出朗读按钮可能就是浮窗上的 X（用户说"左下角自动阅读浮游框点叉关闭"）
——浮窗展开态有 X。重试：点浮窗展开 → 找 X 关闭浮窗+结束会话。"""
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
floats = [(t, b) for t, b in client.recognize("OCR", {}, s).text_boxes()
          if b[1] > 1000 and b[0] > 450 and len(t) <= 2]
print("浮窗:", floats, flush=True)
if floats:
    t, b = floats[0]
    x, y = b[0] + b[2] // 2, b[1] + b[3] // 2
    client.swipe(x, y, x, y, 60)
    time.sleep(2)
    s2 = client.screencap()
    boxes = client.recognize("OCR", {}, s2).text_boxes()
    # 全部打印找 X / 关闭 / 退出
    for t2, b2 in sorted(boxes, key=lambda x: x[1][1]):
        if b2[1] > 800:
            print(f"y={b2[1]:4d} x={b2[0]:4d} w={b2[2]:3d} | {t2}", flush=True)
client.close()
