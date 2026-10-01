"""解码 supervise_r1 v3 首轮：确认 runner 在什么页面、进度如何。"""
from pathlib import Path
import re
from collections import Counter

p = Path(r"G:\project_X\runtime\logs\supervise_r1.log")
text = p.read_text(encoding="utf-8", errors="replace")
rows = text.splitlines()
print("总行数:", len(rows))

# 关键页面特征统计
pat = {
    "奖励页(看小视频领好礼)": "看小视频领好礼",
    "广告卡(立即观看)": "立即观看",
    "广告播放(倒计时/广告)": "广告",
    "广告结果(奖品已发放)": "奖品已发放",
    "12层计数": r"\d+/12",
    "offerwall(跳转详情页)": "跳转详情页",
    "直播间": "进入直播间",
    "验证码": "安全验证",
    "主页": "书架",
}
for name, kw in pat.items():
    cnt = sum(1 for r in rows if kw in r)
    if cnt:
        print(f"{name}: {cnt} 行")

# 最新一条
last = rows[-1]
print("\n最新:", last[:160])
