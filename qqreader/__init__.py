"""QQReader —— QQ 阅读每日任务自动化（MaaFramework 重构）。

分层（对应 AGENTS.md §3.1）：

    page/      页面状态：多特征确认当前处于哪个页面/状态
    contract/  任务契约：start / ready / progress / captcha / success /
               recoverable_error / fatal_error / timeout
    recovery/  恢复：卡住与异常时的升级式兜底策略
    captcha/   验证码：检测、阻塞、求解、求解后确认、人工兜底
    runner/    调度核心：通用状态机执行器（不含任何任务名特判）
    tasks/     广告 / 游戏等具体任务的契约与适配器（专属行为只放这里）

核心（page / contract / recovery / captcha / runner）**不依赖 MaaFramework**，
真实识别与点击通过 ``PageObserver`` / ``TaskAdapter`` / ``DeviceController``
等协议注入，因此可以脱离真机做单元测试。
"""

from .page.states import Orientation, PageState, RunState

__all__ = ["Orientation", "PageState", "RunState"]
__version__ = "0.1.0"
