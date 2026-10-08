"""内容从「躺下吧，戴先生」推进到了「勾玉缓缓地转动」（第35章开头位置）
——刚才 11:41 那轮 toggle 又把自动阅读关了（幂等检测失败后 toggle 翻转）。
而且**自动阅读翻页太慢**：默认速度下 25s 都可能不翻页，判定窗口不可靠。
换个 100% 可靠的判定：**用 toast 文字**。「已开启自动阅读」/「自动阅读中·设置」
面板标题=开的；「已关闭自动阅读」=关的。toggle 后 1.5s 内抓 toast。
重写 enable_auto_read：
1. 点 toggle 后立即（1.5s 内）OCR 找 toast：
   - 「已开启自动阅读」→ 成功开启，返回 True
   - 「已关闭自动阅读」→ 原来是开的被我关了 → 再 toggle 一次 → True
   - 「人声朗读中无法开启」→ 失败 False
2. 不再依赖翻页检测（慢且不稳）。
同时 is_auto_reading 也用面板标题判定（呼菜单看「自动阅读中·设置」），
避免翻页窗口误判。"""
from pathlib import Path

p = Path(r"G:\project_X\scripts\auto_read_30min.py")
src = p.read_text(encoding="utf-8")

old_enable = src[src.find("def enable_auto_read"):src.find("def is_auto_reading")]
new_enable = '''def enable_auto_read() -> bool:
    """幂等呼菜单→设置→点自动阅读，用 toast 文字判定结果（可靠）。"""
    for _ in range(2):
        client.swipe(360, 640, 360, 640, 60)
        time.sleep(1.5)
        texts = " ".join(t for t, b in ocr_all())
        if "设置" in texts:
            break
    client.swipe(452, 1247, 452, 1247, 60)
    time.sleep(1.5)
    client.swipe(355, 1122, 355, 1122, 60)
    time.sleep(1.2)  # toast 窗口
    toast = " ".join(t for t, b in ocr_all())
    client.swipe(360, 640, 360, 640, 0)
    time.sleep(1.5)
    if "已开启自动阅读" in toast:
        log("toast: 已开启自动阅读 ✅")
        return True
    if "已关闭自动阅读" in toast:
        # 原本开着，被我关了 → 再开一次
        log("toast: 已关闭（原本开着）→ 重新开启")
        for _ in range(2):
            client.swipe(360, 640, 360, 640, 60)
            time.sleep(1.5)
            if "设置" in " ".join(t for t, b in ocr_all()):
                break
        client.swipe(452, 1247, 452, 1247, 60)
        time.sleep(1.5)
        client.swipe(355, 1122, 355, 1122, 60)
        time.sleep(1.2)
        toast2 = " ".join(t for t, b in ocr_all())
        client.swipe(360, 640, 360, 640, 0)
        time.sleep(1.5)
        ok = "已开启自动阅读" in toast2
        log(f"二次开启: {ok}")
        return ok
    log(f"toast 未见开启成功: {toast[:60]}")
    return False


'''
src = src.replace(old_enable, new_enable)

old_is = src[src.find("def is_auto_reading"):src.find("def main")]
new_is = '''def is_auto_reading() -> bool:
    """呼菜单看设置面板标题是否为「自动阅读中」——确定性判定。"""
    for _ in range(2):
        client.swipe(360, 640, 360, 640, 60)
        time.sleep(1.5)
        texts = " ".join(t for t, b in ocr_all())
        if "设置" in texts:
            break
    on = "自动阅读中" in texts
    # 收起菜单
    client.swipe(360, 640, 360, 640, 0)
    time.sleep(1.5)
    return on


'''
src = src.replace(old_is, new_is)
p.write_text(src, encoding="utf-8")
print("判定全部改为 toast/面板标题（确定性）")
