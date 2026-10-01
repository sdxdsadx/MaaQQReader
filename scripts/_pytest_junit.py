"""--tb=no 没输出汇总行（-q 模式）？直接数通过的测试数：用 junit-xml。"""
import subprocess

r = subprocess.run(
    ["cmd", "/c", "set PYTHONPATH=G:\\project_X&& D:\\python\\python.exe -m pytest tests/ -q --tb=no --junitxml=G:\\project_X\\runtime\\logs\\final_junit.xml"],
    cwd=r"G:\project_X", capture_output=True, text=True, timeout=280, errors="replace")
out = (r.stdout or "") + (r.stderr or "")
import xml.etree.ElementTree as ET
tree = ET.parse(r"G:\project_X\runtime\logs\final_junit.xml")
root = tree.getroot()
s = root.attrib
print(f"tests={s.get('tests')} failures={s.get('failures')} errors={s.get('errors')} skipped={s.get('skipped')}")
