"""修正②：听书任务结束后自动领取 +20。
daily_all.py 的 run() 在 DailyAudiobookFlow 成功后插入「去奖励页点
立即领取」动作。用独立函数实现（复用现有 OCR 逻辑）。"""
from pathlib import Path

p = Path(r"G:\project_X\scripts\daily_all.py")
src = p.read_text(encoding="utf-8")

anchor = """def main() -> int:"""
addition = '''def claim_audiobook_reward() -> bool:
    """听书 SUCCESS 后去奖励页领「每日听书30分钟+20赠币」。
    路径：书架 → 时长兑赠币入口 → 下滑找听书卡「立即领取」→ 点。"""
    import subprocess
    import sys as _sys
    _ROOT2 = Path(__file__).resolve().parents[1]
    if str(_ROOT2) not in _sys.path:
        _sys.path.insert(0, str(_ROOT2))
    from qqreader.config import load_config
    from qqreader.maa.factory import build_maa_client

    config = load_config("configs/qqreader.local.json")
    client = build_maa_client(config)
    try:
        client.connect()
    except Exception as exc:
        print(f"[听书领取] 连接失败: {exc}", flush=True)
        return False

    def ocr():
        s = client.screencap()
        return client.recognize("OCR", {}, s).text_boxes()

    try:
        # 回书架
        s = client.screencap()
        if not any(t.strip() == "书架" and b[1] < 100 for t, b in ocr()):
            client.swipe(89, 1263, 89, 1263, 60)
            time.sleep(2.5)
        # 点时长兑赠币入口
        s = client.screencap()
        entry = [(t, b) for t, b in ocr() if "兑赠币" in t or "领20赠币" in t]
        if not entry:
            print("[听书领取] 未找到奖励入口", flush=True)
            return False
        t, b = entry[-1]
        client.swipe(b[0] + b[2] // 2, b[1] + b[3] // 2, b[0] + b[2] // 2, b[1] + b[3] // 2, 60)
        time.sleep(4)
        # 下滑找听书卡「立即领取」
        for _ in range(5):
            s = client.screencap()
            boxes = ocr()
            card = [(t, b) for t, b in boxes if "每日听书" in t or "已听" in t]
            claim = [(t, b) for t, b in boxes if t.strip() == "立即领取"]
            if card and claim:
                nearby = [c for c in claim if abs(c[1][1] - card[0][1][1]) < 150]
                if nearby:
                    t, b = nearby[0][1]
                    client.swipe(b[0] + b[2] // 2, b[1] + b[3] // 2,
                                 b[0] + b[2] // 2, b[1] + b[3] // 2, 60)
                    time.sleep(2.5)
                    print("[听书领取] ✅ 已点立即领取", flush=True)
                    return True
            client.swipe(360, 1100, 360, 600, 450)
            time.sleep(1.8)
        print("[听书领取] 未找到听书卡领取按钮（可能已领）", flush=True)
        return False
    finally:
        client.close()


def main() -> int:'''
assert anchor in src
src = src.replace(anchor, addition, 1)

# 在主循环里：听书成功后调用领取
old = """    for task, extra in plan:
        ok, dt = run(task, extra)
        results.append((task, ok, dt))
        time.sleep(5)  # 任务间缓冲，避免设备并发"""
new = """    for task, extra in plan:
        ok, dt = run(task, extra)
        results.append((task, ok, dt))
        if task == "DailyAudiobookFlow" and ok:
            try:
                claim_audiobook_reward()
            except Exception as exc:
                print(f"[听书领取] 异常: {exc}", flush=True)
        time.sleep(5)  # 任务间缓冲，避免设备并发"""
assert old in src
src = src.replace(old, new)
p.write_text(src, encoding="utf-8")
print("daily_all.py 听书自动领取已加")
