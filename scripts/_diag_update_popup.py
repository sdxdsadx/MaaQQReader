"""发现「安装新版本」升级弹窗（observe 1/21 有）！它可能挡住一切——
observe 184 还在循环说明弹窗一直在或关掉后页面仍 UNKNOWN。
弹窗有「安装新版本」按钮。popup_recoverable(keys) 会处理吗？
popup_close 特征指向弹窗 X。真正问题可能是弹窗反复弹（自动下载后再次弹）。

直接看当前模拟器有没有升级弹窗（活体截图找「安装新版本」）。"""
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
hit = [(t, b) for t, b in boxes if "安装" in t or "更新" in t or "升级" in t]
print("升级弹窗痕迹:", hit if hit else "无")
client.close()
