"""dev/resource/pipeline 不在 git 里（无历史）。[Anchor] 语法其实可能是
MAA 的合法 anchor 语法？MAA v5 支持 <Anchor>? 查官方:MAA 用 <...> 作
anchor 前缀？不对——查 dev 下其他文件是否已有 [Anchor] 用法及运行验证。
更快：听书 02:15 那轮（修改前）成功，04:53（修改后）失败——但断链节点
AdReturnStable 在广告链，不在听书链！MAA 资源加载时全部 json 都解析——
若 [Anchor] 语法非法会导致所有 legacy flow 失败。02:15 成功→04:53 失败
之间 json 被改。看文件 mtime 和 AudiobookPauseAfterTrial 的 next 变更
（第一棒说改了它）。"""
import json
import time
from pathlib import Path

pf = Path(r"G:\project_X\dev\resource\pipeline\qq_reader_trial.json")
print("mtime:", time.strftime("%H:%M:%S", time.localtime(pf.stat().st_mtime)))
data = json.loads(pf.read_text(encoding="utf-8"))
for k in ("AudiobookPauseAfterTrial", "AudiobookPlaying", "AudiobookWaitOneMinute"):
    v = data.get(k)
    print(k, "->", v.get("next") if v else "MISSING", "| post_delay:", v.get("post_delay") if v else "-")
