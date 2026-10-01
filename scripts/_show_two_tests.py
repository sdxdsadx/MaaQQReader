"""剩余 12 个失败的分析与修复：
1. 'MuMuManager info -v all did not contain any emulator instance'
   → ParsesSingleInstanceOutputWithoutWrappingMap：ParseInstances 对
   单实例非嵌套输出兼容没做好。看测试输入。
2. '脚本入口不存在/工作目录不存在' → Codex 写的 TaskConfigurationValidatorTests
   期待 Validate() 抛（旧 fail-fast 语义）。我把检查挪到了 CreateAsync。
   这几个测试应改为直接调 ValidateScriptPathsExist（public 了）。
3. Assert.Contains/Equal/False/Single/Throws-no-exception → 需逐个看。
先看 1 和 2 的测试代码。"""
from pathlib import Path

t = Path(r"D:\游戏文件\chatgpt\gameflow\tests\Gameflow.Infrastructure.Windows.Tests\MuMuInstanceDiscoveryTests.cs")
src = t.read_text(encoding="utf-8")
i = src.find("ParsesSingleInstanceOutputWithoutWrappingMap")
print(src[i-20:i+900])
print("=====")
v = Path(r"D:\游戏文件\chatgpt\gameflow\tests\Gameflow.Infrastructure.Windows.Tests\TaskConfigurationValidatorTests.cs")
vsrc = v.read_text(encoding="utf-8")
j = vsrc.find("ReportsMissingScriptEntryPointInsteadOfFailingAtLaunch")
print(vsrc[j-20:j+900])
