"""11:05 首行变了（青水笑呵呵… vs 之前 办，凯…打卡）——说明第一次
11:02 的 toggle 实际把自动阅读**关了**，但现在首行静止 → 又不在自动阅读。
脚本 11:06 两次 toggle+验证都 False——问题可能在 toggle 序列本身：
呼菜单→设置→点自动阅读后，面板还开着（菜单未收起），正文被面板挡住，
「body_first_line」读的是面板遮挡后的区域或面板停留导致首行读取稳定。
修：toggle 后先按 BACK 收起面板/菜单再等翻页。
另外「自动阅读」点击后面板自动收起（app 通常如此），但保险起见 BACK 一下。
改 enable_auto_read：toggle 后 sleep(1) + BACK 收起面板 → 再验证翻页。"""
from pathlib import Path

p = Path(r"G:\project_X\scripts\auto_read_30min.py")
src = p.read_text(encoding="utf-8")
old = """    client.swipe(355, 1122, 355, 1122, 60)
    time.sleep(2)
    l1 = body_first_line()
    time.sleep(9)
    l2 = body_first_line()"""
new = """    client.swipe(355, 1122, 355, 1122, 60)
    time.sleep(1.5)
    # 收起可能残留的设置面板/菜单，避免遮挡正文首行
    client.swipe(360, 640, 360, 640, 0)
    time.sleep(1.5)
    l1 = body_first_line()
    time.sleep(9)
    l2 = body_first_line()"""
assert old in src
src = src.replace(old, new)
p.write_text(src, encoding="utf-8")
print("toggle 后加 BACK 收面板")
