"""修 TaskConfigurationValidatorTests 的 2 个 fail-fast 测试：
Validate() 不再抛路径问题 → 改为直接调 ValidateScriptPathsExist。"""
from pathlib import Path

v = Path(r"D:\游戏文件\chatgpt\gameflow\tests\Gameflow.Infrastructure.Windows.Tests\TaskConfigurationValidatorTests.cs")
src = v.read_text(encoding="utf-8")

old1 = """            var issues = TaskConfigurationValidator.Validate(configuration);

            var issue = Assert.Single(issues, item => item.Field == "脚本入口与启动设置");
            Assert.Contains("missing-runner.exe", issue.Message);
            Assert.Contains("不存在", issue.Message);"""
new1 = """            // 存在性 fail-fast 已移至运行前（CreateAsync），编辑期不拦截相对路径。
            var error = Assert.Throws<InvalidOperationException>(
                () => TaskConfigurationValidator.ValidateScriptPathsExist(configuration.ScriptProfile));

            Assert.Contains("missing-runner.exe", error.Message);
            Assert.Contains("不存在", error.Message);"""
assert old1 in src
src = src.replace(old1, new1)
v.write_text(src, encoding="utf-8")
print("Validator 测试 1 已改")
