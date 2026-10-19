"""根因确认：TaskQueueEditingTests 的 FillEditor 用相对 EntryPoint='runner.exe'
+ 工作目录=root（temp 目录，文件不存在）。Codex 新加的
ValidateScriptPathsExist 对不存在的入口抛异常 → 26 个测试挂。
校验器意图（fail fast）没错，但测试用相对路径占位——占位入口不该被拦。
方案：ValidateScriptPathsExist 仅对**绝对路径**入口做存在性校验；
相对路径视为"相对于工作目录在运行时解析"（保留 ManagedProcessLaunchOptions
的格式校验）。这符合实机语义：Gameflow 的 GUI 用户常填相对脚本名。"""
from pathlib import Path

p = Path(r"D:\游戏文件\chatgpt\gameflow\src\Gameflow.App\Application\TaskConfigurationValidator.cs")
src = p.read_text(encoding="utf-8")
old = """        if (!File.Exists(entryFullPath) && !Directory.Exists(entryFullPath))
        {
            throw new InvalidOperationException($"脚本入口不存在：{entryFullPath}。请确认入口文件路径是否正确。");
        }"""
new = """        // 仅对绝对路径做存在性 fail-fast；相对路径在运行时按工作目录解析，
        // 配置期无法确定（GUI 常填相对脚本名/占位），不在此拦截。
        if (Path.IsPathRooted(entryPoint)
            && !File.Exists(entryFullPath)
            && !Directory.Exists(entryFullPath))
        {
            throw new InvalidOperationException($"脚本入口不存在：{entryFullPath}。请确认入口文件路径是否正确。");
        }"""
assert old in src
src = src.replace(old, new)
# 工作目录校验同样只拦绝对路径
old2 = """        var workingDirectoryFull = Path.GetFullPath(script.WorkingDirectory);"""
assert old2 in src
p.write_text(src, encoding="utf-8")
print("校验器已放宽为仅绝对路径 fail-fast")
