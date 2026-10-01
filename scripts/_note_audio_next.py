"""节点定义看起来合法（OCR → ClickKey key=4 = BACK，max_hit=4 防死循环）。
为什么 4000？MAA v5 的 ClickKey action？MAA v5 里按键动作用 action="ClickKey"
配 "key": 4 是合法的（key 是 Android keycode, 4=BACK）。
4000 = internal error。可能原因是 json 里其他改动。最直接的验证：单独跑
听书任务看现在（我已修 [Anchor] 断链）是否成功——如果还 4000 再深挖。
但广告任务正在跑（05:15 启动，还有 ~35min）。等广告完成后单独跑听书。"""
print("等广告完成后单独验证听书")
