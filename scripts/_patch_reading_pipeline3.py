"""「去阅读」Click 点了 (376,505)？expected=去阅读 但 box=[0,0,720,1280] 全屏
DirectHit——没用 expected 定位！Click 落在屏幕中心 (376,505)，点到了页面中间
（+20 区域）→ 没跳去阅读。RA 兑现: expected 只是识别字符，点击坐标=识别框。
但 box 全屏说明 MAA 没把 expected 当 OCR 目标（DirectHit 而非 OCR）——
因为该节点没写 recognition 字段！expected 需要 recognition: OCR 才生效。

修正 RewardGotoReading: 加 "recognition": "OCR"（MAA v5 语法：
{"recognition":"OCR","expected":"去阅读",...}）。ReadingGotoShelf 同样修正。"""
import json
from pathlib import Path

pf = Path(r"G:\project_X\dev\resource\pipeline\qq_reader_trial.json")
data = json.loads(pf.read_text(encoding="utf-8"))

data["RewardGotoReading"] = {
    "recognition": "OCR",
    "expected": "去阅读",
    "action": "Click",
    "post_delay": 2500,
    "next": ["ReadingFindBookTerminal", "ReadingFindBookByTitleTerminal",
             "ReadingOpenFirstShelfBookTerminal"],
    "focus": {"RewardGotoReading": "奖励页点「去阅读」跳回阅读侧，再找书"},
}
data["ReadingGotoShelf"] = {
    "recognition": "OCR",
    "expected": "书架",
    "roi": [0, 1150, 300, 130],
    "action": "Click",
    "post_delay": 2000,
    "next": ["ReadingFindBookTerminal", "ReadingFindBookByTitleTerminal",
             "ReadingOpenFirstShelfBookTerminal"],
    "focus": {"ReadingGotoShelf": "底部「书架」tab 回书架页再找书"},
}
pf.write_text(json.dumps(data, ensure_ascii=False, indent=4) + "\n", encoding="utf-8")
print("已改为 OCR 识别点击")
