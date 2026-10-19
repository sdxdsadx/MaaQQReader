"""进度条只有 6 分钟——第二轮 35min 挂机后阅读时长没涨（还是差 4 分钟）！
而第一轮挂机涨了 3 分钟。观察到的规律：**挂机中页面静止（自动阅读没开），
QQ阅读服务器只累计「真实翻页阅读时长」，纯挂机打折/不计**。
昨天发现 9min 挂机只计 3 分钟——同样规律。
这正说明：**必须开「自动阅读」翻页**（昨天 auto_read_30min.py 方案），
否则挂机时长不计入。这是今天最重要的观察问题 → 提交 issue 让 Codex 把
DirectReadingFlow 挂机节点改成「开自动阅读」模式（菜单→设置→自动阅读 +
toast 判定 + 30min 后处理休息弹窗），替代纯静止挂机。
先看现在差 4 分钟：用 auto_read_30min.py 补 4 分钟（脚本可传时长），
手动恢复后领币。先看 auto_read 脚本是否支持自定义时长。"""
import sys
from pathlib import Path

src = Path(r"G:\project_X\scripts\auto_read_30min.py").read_text(encoding="utf-8")
import re
m = re.search(r"def main\(.*?\n(.*?)duration = (.*?)(\n)", src, re.S)
print(src[src.find("def main"):src.find("def main")+400])
