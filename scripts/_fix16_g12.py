"""11 个失败分 3 组修：
组1 ValidatorTests(2)：ReportsMissingWorkingDirectory / ReportsMissingScriptEntryPoint
   → 这俩期待 Validate() 拦截；我把存在性检查挪到 CreateAsync 了。
   但 RejectsWrongClientResolutionBeforeAnyInput(ScriptLaunch) 和 RejectsElevated
   都在 ScriptLaunchConfigurationTests 里期待 CreateAsync 阶段抛。
   统一语义：**Validate() 保留绝对路径存在性检查**（配置里绝对路径=用户明确
   指定，必须存在），**CreateAsync 也调用**（双保险）。相对路径两边都不拦。
   → 把 ValidateScriptPathsExist 加回 Validate 主链，但仅绝对路径拦（已是）。
   之前 26 失败是因为"相对路径也拦"；现在只拦绝对，TaskQueueEditing 的
   runner.exe（相对）不拦；而 ValidatorTests 用的是绝对 temp 路径（不存在）
   → 会拦 → 这正是它期待的。
组2 ParseMuMuReportsConfiguredManagerPathThatDoesNotExist：
   我把 File.Exists 检查去掉了 → 恢复抛 InvalidOperationException（测试期待），
   但 ResolveManagerPathExplains 测试期待 FileNotFoundException——分开：
   配置路径不存在 → InvalidOperationException("配置的 MuMuManager 路径不存在")
   探测失败 → FileNotFoundException。恢复 File.Exists 抛 InvalidOperationException。
组3 RuntimeFactoryClosesTarget(failScript True/False) + ScriptLaunch 4 个：
   看具体错误再修。"""
from pathlib import Path

# 组1：恢复 Validate 主链中的存在性检查
val = Path(r"D:\游戏文件\chatgpt\gameflow\src\Gameflow.App\Application\TaskConfigurationValidator.cs")
src = val.read_text(encoding="utf-8")
old = """        Check(issues, "脚本入口与启动设置", () =>
        {
            _ = ManagedProcessLaunchOptions.FromScript(configuration.ScriptProfile);
        });"""
new = """        Check(issues, "脚本入口与启动设置", () =>
        {
            _ = ManagedProcessLaunchOptions.FromScript(configuration.ScriptProfile);
            ValidateScriptPathsExist(configuration.ScriptProfile);
        });"""
assert old in src
src = src.replace(old, new)
val.write_text(src, encoding="utf-8")

# 组2：恢复配置路径不存在的即时报错
fac = Path(r"D:\游戏文件\chatgpt\gameflow\src\Gameflow.App\Application\WindowsTaskRuntimeFactory.cs")
fsrc = fac.read_text(encoding="utf-8")
old2 = """            managerPath = hasConfiguredPath
                ? path  // 配置路径的存在性在运行期由 MuMuTargetAdapter 校验并给出完整探测报告
                : (managerPathResolver ?? MuMuTargetAdapter.ResolveManagerPath)(null);"""
new2 = """            managerPath = hasConfiguredPath
                ? File.Exists(path)
                    ? path
                    : throw new InvalidOperationException($"配置的 MuMuManager 路径不存在：{path}")
                : (managerPathResolver ?? MuMuTargetAdapter.ResolveManagerPath)(null);"""
assert old2 in fsrc
fsrc = fsrc.replace(old2, new2)
fac.write_text(fsrc, encoding="utf-8")
print("组1/组2 已修")
