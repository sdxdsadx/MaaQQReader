"""浏览类广告（喇叭广告）卡住：文案「去体验9秒」「上滑或点击跳转到详情」。
OCR 尾部 100+ observe 同页面——这是 live_texts 未覆盖的新变体：
「上滑或点击跳转到详情」不在 live_texts（有'上滑浏览获取奖励'/'需要下滑'），
也没 offer_texts（'了解详情/跳转详情页或第三方应用'）。「去体验9秒」也不在。
→ adapter 无分支命中 → 走 waits 计时 → 12 次后 press_back——但这是
浏览型广告，BACK 无效需 X/滑动。251 observe 反复。

修复：live_texts 加「上滑或点击」「去体验」——归入 live 广告处理（下滑浏览）。
这最小改动且处理路径现成（_handle_live_ad 下滑 N 次后 X 退出）。
run 还在跑，先停掉。"""
from pathlib import Path

p = Path(r"G:\project_X\qqreader\tasks\ad.py")
src = p.read_text(encoding="utf-8")
old = """        live_texts: tuple = (
            "进入直播间",
            "直播中",
            "需要下滑",
            "上滑或点击",
            "扭一扭或点击",
            "下滑",
        ),"""
new = """        live_texts: tuple = (
            "进入直播间",
            "直播中",
            "需要下滑",
            "上滑或点击",
            "扭一扭或点击",
            "下滑",
            "去体验",
        ),"""
assert old in src
src = src.replace(old, new)
p.write_text(src, encoding="utf-8")
print("live_texts +去体验")
