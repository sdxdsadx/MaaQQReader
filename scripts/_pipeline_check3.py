import json

j = json.load(open(r"G:\project_X\dev\resource\pipeline\qq_reader_trial.json", encoding="utf-8"))
for name in ("ReadingFindBookTerminal", "ReadingFindBookByTitleTerminal",
             "ReadingOpenFirstShelfBookTerminal", "ReadingWaitOneMinute",
             "ReadingExitAfterTimer"):
    print(f"--- {name}")
    print(json.dumps(j.get(name, {}), ensure_ascii=False, indent=1)[:900])
