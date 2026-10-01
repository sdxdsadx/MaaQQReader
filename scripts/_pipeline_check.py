import json

j = json.load(open(r"G:\project_X\dev\resource\pipeline\qq_reader_trial.json", encoding="utf-8"))
print("节点总数:", len(j))
for name in ("DirectReadingFlow", "ReadingWaitOneMinute", "DailyAudiobookFlow",
             "AudiobookWaitOneMinute", "DailyAdFlow"):
    if name in j:
        n = j[name]
        print(f"{name}: next={n.get('next')} | post_delay={n.get('post_delay')} | recognition={n.get('recognition')}")
    else:
        print(f"{name}: 不存在")
