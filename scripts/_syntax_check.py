import ast
src = open(r"G:\project_X\scripts\auto_read_30min.py", encoding="utf-8").read()
ast.parse(src)
print("syntax ok, lines:", len(src.splitlines()))
