"""ReportsMissingWorkingDirectory 改为新语义：Validate 不抛，目录自动创建。
改成验证"自动创建目录"行为。"""
from pathlib import Path

tv = Path(r"D:\游戏文件\chatgpt\gameflow\tests\Gameflow.Infrastructure.Windows.Tests\TaskConfigurationValidatorTests.cs")
tsrc = tv.read_text(encoding="utf-8")
old = """            var issues = TaskConfigurationValidator.Validate(configuration);

            var issue = Assert.Single(issues, item => item.Field == "脚本入口与启动设置");
            Assert.Contains("工作目录", issue.Message);"""
new = """            var issues = TaskConfigurationValidator.Validate(configuration);

            Assert.DoesNotContain(issues, item => item.Field == "脚本入口与启动设置");
            Assert.True(Directory.Exists(Path.Combine(
                Path.GetTempPath(), "gameflow-validation")), "工作目录应被自动创建");"""
assert old in tsrc
tsrc = tsrc.replace(old, new)
tv.write_text(tsrc, encoding="utf-8")
print("ReportsMissingWorkingDirectory 已改为自动创建语义")
