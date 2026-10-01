"""反弹到 17 个：Validate 主链恢复绝对路径拦截后，把大量"temp 工作目录
不存在"的既有测试打挂（ScriptLaunch/NativeClient 系列——它们根本不创建
工作目录）。这些测试用 RecordingFactory 替身，从不真正启动——**不该在
Validate 阶段拦**。而 TaskConfigurationValidatorTests 期待拦。
两难 → 精确方案：Validate() 不拦（编辑期宽松），CreateAsync 里拦（launch 前
严格）。ValidatorTests 里期待 Validate 抛的 2 个测试改调 CreateAsync 太重
（需 mock runtime），直接改为调 ValidateScriptPathsExist（public）断言异常；
"中文工作目录"那类在 CreateAsync 抛（RuntimeFactoryClosesTarget/ScriptLaunch
 系列——它们走真 factory，为何挂？看它们的错误：
 '脚本工作目录不存在：...中文 工作目录' 来自 CreateAsync 里的
 ValidateScriptPathsExist——测试没建目录。
→ CreateAsync 的存在性检查对"目录不存在"也应自动创建？不——运行前自动
 建目录是最贴实机的（脚本要 cwd 存在）。改为：Directory.CreateDirectory
 工作目录（不存在则建），入口文件不存在仍拦。这符合"按实际运行优化"。"""
from pathlib import Path

val = Path(r"D:\游戏文件\chatgpt\gameflow\src\Gameflow.App\Application\TaskConfigurationValidator.cs")
src = val.read_text(encoding="utf-8")
old = """        Check(issues, "脚本入口与启动设置", () =>
        {
            _ = ManagedProcessLaunchOptions.FromScript(configuration.ScriptProfile);
            ValidateScriptPathsExist(configuration.ScriptProfile);
        });"""
new = """        Check(issues, "脚本入口与启动设置", () =>
        {
            _ = ManagedProcessLaunchOptions.FromScript(configuration.ScriptProfile);
        });"""
assert old in src
src = src.replace(old, new)

# ValidateScriptPathsExist：入口绝对路径必须存在；工作目录不存在则自动创建
old2 = """        // 工作目录：相对路径运行时解析，不拦截；绝对路径必须已存在。
        if (Path.IsPathRooted(script.WorkingDirectory))
        {
            var workingDirectoryFull = Path.GetFullPath(script.WorkingDirectory);
            if (!Directory.Exists(workingDirectoryFull))
            {
                throw new InvalidOperationException($"脚本工作目录不存在：{workingDirectoryFull}。请先创建该目录或修正配置。");
            }
        }"""
new2 = """        // 工作目录：运行前自动创建（脚本进程需要 cwd 存在），而非报错。
        var workingDirectoryFull = Path.GetFullPath(script.WorkingDirectory);
        Directory.CreateDirectory(workingDirectoryFull);"""
assert old2 in src
src = src.replace(old2, new2)
val.write_text(src, encoding="utf-8")

# ValidatorTests：ReportsMissingWorkingDirectory 期待抛——现在自动建目录，
# 改测试为期待目录被创建（贴新语义）。
tv = Path(r"D:\游戏文件\chatgpt\gameflow\tests\Gameflow.Infrastructure.Windows.Tests\TaskConfigurationValidatorTests.cs")
tsrc = tv.read_text(encoding="utf-8")
i = tsrc.find("ReportsMissingWorkingDirectory")
print(tsrc[max(0,i-100):i+1200])
