import json

j = json.load(open(r"G:\project_X\dev\resource\pipeline\qq_reader_trial.json", encoding="utf-8"))
for name in ("ReadingFindBookTerminal", "ReadingFindBookByTitleTerminal",
             "ReadingOpenFirstShelfBookTerminal", "ReadingExitAfterTimer",
             "AudiobookPlaying", "AudiobookFindBook", "AudiobookOpenFirstShelfBook",
             "AudiobookBackUntilShelf", "AudiobookPauseAfterTrial"):
    if name not in j:
        print(f"{name}: 不存在")
        continue
    n = j[name]
    rec = n.get("recognition") or {}
    print(f"--- {name}")
    print(f"  recognition={n.get('recognition_type') or rec} | expected={str(n.get('expected') or n.get('target'))[:80]}")
    print(f"  roi={n.get('roi')} | action={n.get('action')} | next={n.get('next')}")
    print(f"  timeout={n.get('timeout')} | overview={str(n.get('overview'))[:60]}")
