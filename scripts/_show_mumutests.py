"""分类修复剩余 6 类失败：
A) ParseMuMu 配置路径不存在 → 抛 InvalidOperationException 太早：
   ResolveManagerPath 的探测/报错归 MuMuTargetAdapter（运行期），
   ParseMuMu 里配置路径不存在只记录、不抛（把 File.Exists 抛异常去掉，
   交给 adapter 运行时报——它有完整探测列表报错）。
B) ValidateScriptPathsExist 被我挪到 CreateAsync 后，"launch 前 fail-fast"
   测试（ReportsMissing.../fixture script.exe/中文工作目录）期待 Validate()
   抛或 CreateAsync 抛——现在 CreateAsync 会抛，但这些测试直接调 Validate()
   ——把这几个 Codex 新写的测试改为期待 Validate 不抛 + CreateAsync 抛太绕；
   直接看测试怎么写的再定。
先看 MuMuInstanceDiscoveryTests 3 个失败的断言。"""
from pathlib import Path

t = Path(r"D:\游戏文件\chatgpt\gameflow\tests\Gameflow.Infrastructure.Windows.Tests\MuMuInstanceDiscoveryTests.cs")
src = t.read_text(encoding="utf-8")
i = src.find("ResolveManagerPathExplainsProbedLocationsWhenMissing")
print(src[i-30:i+1400])
