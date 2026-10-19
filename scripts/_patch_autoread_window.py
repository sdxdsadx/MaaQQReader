"""问题定位：正文页 OCR 显示右上角有 "m"(x=686,y=105) 小字残留，且
body_first_line 过滤条件 100<y<1000 读到的第一行「和药物的调节」——
页面在自动阅读下其实**翻过了**（内容与 11:12 的「保持着持续的关注」
不同），但脚本验证窗口 12s 内翻页速度慢（自动阅读约 10~15s 一屏），
9s 等待不够 + 首行可能两次都取到同一段。
修：验证窗口 9s→15s，且比较两次读数中间隔 12s。再看护循环本来 60s
一测没大问题。还有个坑：toggle 后 BACK 收面板可能又把「自动阅读」
面板确认弹窗顶掉？总之先把验证窗口拉长试一次。"""
from pathlib import Path

p = Path(r"G:\project_X\scripts\auto_read_30min.py")
src = p.read_text(encoding="utf-8")
old = """    l1 = body_first_line()
    time.sleep(9)
    l2 = body_first_line()"""
new = """    l1 = body_first_line()
    time.sleep(15)
    l2 = body_first_line()"""
assert old in src
src = src.replace(old, new)
p.write_text(src, encoding="utf-8")
print("验证窗口 9s→15s")
