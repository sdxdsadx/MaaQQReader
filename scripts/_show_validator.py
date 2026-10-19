"""定位 TaskQueueEditingTests 26 个失败的调用源头：它们构造
WindowsTaskRuntimeFactory 或经 SingleTaskRunService 走 CreateAsync 触发
ValidateScriptPathsExist。看 TaskConfigurationValidator 的入口
（哪个公开方法调用 ValidateScriptPathsExist）。"""
from pathlib import Path

src = Path(r"D:\游戏文件\chatgpt\gameflow\src\Gameflow.App\Application\TaskConfigurationValidator.cs").read_text(encoding="utf-8")
print(src[:1800])
