"""真相：菜单本来就开着（初始就有 目录/设置）！我的第一步「呼菜单」
点了屏幕中央反而把菜单**收起**了，后面点 (452,1247) 点到正文空白处、
点 (355,1122) 点到正文——全部无效，还好没乱翻页。
根因：多次探针脚本里「呼菜单」toggle 导致菜单时开时关，状态不可预期。
修正策略（自适应）：呼菜单后检测——若无「设置」标记则说明菜单本来开着，
这次点击把它收了 → **再点一次中央重新呼出**。
即：呼菜单改为幂等（do-while 直到检测到「设置」可见，最多 2 次）。"""
from pathlib import Path

p = Path(r"G:\project_X\scripts\auto_read_30min.py")
src = p.read_text(encoding="utf-8")
old = """    client.swipe(360, 640, 360, 640, 60)
    time.sleep(1.5)
    client.swipe(452, 1247, 452, 1247, 60)
    time.sleep(1.5)"""
new = """    # 幂等呼菜单：点中央后若没看到「设置」说明菜单原本开着被收起，再点一次
    for _ in range(2):
        client.swipe(360, 640, 360, 640, 60)
        time.sleep(1.5)
        s = client.screencap()
        if any("设置" in t for t, b in client.recognize("OCR", {}, s).text_boxes()):
            break
    client.swipe(452, 1247, 452, 1247, 60)
    time.sleep(1.5)"""
assert old in src
src = src.replace(old, new)
p.write_text(src, encoding="utf-8")
print("呼菜单已改幂等")
