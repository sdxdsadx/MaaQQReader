"""junit 根元素结构不同，遍历读 testsuite 属性。"""
import xml.etree.ElementTree as ET

tree = ET.parse(r"G:\project_X\runtime\logs\final_junit.xml")
root = tree.getroot()
print("root tag:", root.tag)
for elem in root.iter():
    if elem.tag.endswith("testsuite"):
        print({k: elem.attrib.get(k) for k in ("tests", "failures", "errors", "skipped")})
        break
else:
    # 打印全部 testsuite
    suites = root.findall(".//testsuite")
    for s in suites:
        print(s.attrib.get("name"), {k: s.attrib.get(k) for k in ("tests", "failures", "errors")})
