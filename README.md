<!-- markdownlint-disable MD033 MD041 -->

<p align="center">
  <img alt="LOGO" src="https://cdn.jsdelivr.net/gh/MaaAssistantArknights/design@main/v1/icons/maa-logo_512x512.png" width="256" height="256" />
</p>

<div align="center">

# MaaQQReader

**基于 [MaaFramework](https://github.com/MaaXYZ/MaaFramework) 的 QQ 阅读自动化 GUI**

日常签到、阅读、听书、游戏、广告、外部应用入口的图形化自动化小助手。

</div>

---

## 简介

MaaQQReader 是一个面向 Windows 的 **QQ 阅读每日任务自动化工具**，基于新一代图像识别框架 [MaaFramework](https://github.com/MaaXYZ/MaaFramework) 开发，通过图形界面（GUI）驱动，采用图像识别 + 模拟输入的方式完成每日必做的阅读、听书、游戏、广告、等级页等任务，并自动串联为一条「每日任务流水线」。

> 驱动引擎：MaaFramework（基于 [MAA](https://github.com/MaaAssistantArknights/MaaAssistantArknights) 开发经验重写的黑盒自动化框架）。

---

## 功能特性

- **图形化界面**：`gui/maa_qq_reader_gui.py` 提供可视化操作面板（任务选择、开始、日志）。
- **每日任务流水线**（`TRIAL_PLAN`）：
  - 启动 QQ 阅读并关闭开屏弹窗
  - 每日自动阅读（默认 2 次 × 35 分钟）
  - 每日听书（默认 35 分钟，结束后暂停）
  - 每日游戏（默认 25 分钟）
  - 每日广告完整流程（自动至 12/12）
  - 外部应用每日流程（大众点评 + 百度地图）
  - 等级页广告每日流程（赠币 + 积分）
  - 领取全部已完成奖励
- **验证码处理**：内置验证码识别/滑块求解（`tools/captcha_solver.py`、`slide_captcha_solver.py`）。
- **模拟器接入**：通过 ADB 连接 MuMu 模拟器，自动连接、检测黑屏、重连。
- **OCR 识别**：依赖 `assets/MaaCommonAssets` 子模块中的 PPOCR 模型（v3/v4/v5/v6 多版本）。

---

## 目录结构

```text
MaaQQReader/
├── gui/
│   └── maa_qq_reader_gui.py      # 图形界面主程序
├── agent/
│   ├── main.py                   # MaaFramework agent 入口
│   ├── my_action.py              # 自定义动作
│   └── my_reco.py                # 自定义识别
├── assets/
│   ├── interface.json            # 界面/场景定义
│   ├── MaaCommonAssets/          # 子模块：OCR 模型等公共资产（git submodule）
│   └── resource/                 # 图片、pipeline 定义
├── tools/                        # 辅助脚本：验证码、点击、阅读监控、模拟器截图等
├── third_party/QQReadScript/     # 外部应用(大众点评/百度地图)流程脚本
├── docs/                         # 文档（CAPTCHA/GUI/TRIAL_PLAN/开发指南）
├── deps/                         # 依赖 schema/工具
├── MaaQQReaderGUI.spec           # PyInstaller 打包配置
├── maatools.config.mts           # maa-tools 配置
├── package.json / pnpm-lock.yaml # Node 工具依赖(maa-tools)
└── 启动可视化界面.cmd
```

---

## 环境要求

- **Windows 10/11**（x64）
- **模拟器**：MuMu 12（开启 ADB）
- **Python**：3.8+（仅运行脚本时；GUI 通常随打包版分发）
- **Node.js**（仅开发/构建 `maa-tools` 相关时）
- **依赖**：见 `tools/requirements.txt`、`package.json`

---

## 快速开始

### 方式一：使用打包版（推荐）

1. 从 Release 下载 `MaaQQReaderGUI.exe`（或运行 `启动可视化界面.cmd`）。
2. 启动 MuMu 模拟器并开启 ADB。
3. 打开 GUI，填写模拟器端口，点击「连接模拟器」。
4. 点击「开始执行所选任务」。

### 方式二：从源码运行

1. 克隆本仓库（**含子模块**，否则 OCR 模型缺失）：
   ```powershell
   git clone --recurse-submodules https://github.com/sdxdsadx/MaaQQReader.git
   cd MaaQQReader
   git submodule update --init --recursive
   ```
2. 安装 Python 依赖：
   ```powershell
   pip install -r tools/requirements.txt
   ```
3. 启动 GUI：
   ```powershell
   python gui\maa_qq_reader_gui.py
   ```

---

## 构建打包

```powershell
# 安装开发依赖后，用 PyInstaller 按 MaaQQReaderGUI.spec 构建
pyinstaller MaaQQReaderGUI.spec
```

---

## 免责声明

> ⚠️ **使用本项目即表示您已阅读、理解并同意以下全部条款。**若不同意，请立即停止使用并删除全部相关文件。

1. **用途限制**：本项目仅用于**个人学习、研究与技术交流**，不应用于任何违反法律法规、应用服务协议的行为。使用者**自行承担**因使用本项目产生的账号处罚、封禁、数据丢失或其它后果。

2. **非官方产品**：本项目与应用方（如 QQ 阅读）、模拟器厂商、底层框架（MaaFramework/MAA）**无任何隶属、许可或合作关系**。MaaFramework、MAA、`assets/MaaCommonAssets` 等第三方资源归其各自作者所有，其分发与使用遵循各自上游的开源协议。

3. **风险自负**：自动化行为可能触发应用反作弊/风控检测、导致账号异常、影响正常使用体验。使用者应自行评估并承担全部风险。作者**不保证**本工具在任何环境下的稳定性、正确性、可用性，亦**不对**因使用本工具造成的直接或间接损失（账号损失、虚拟资产损失、数据丢失、硬件损坏、时间浪费等）承担责任。

4. **无担保**：本项目按“**现状**”（AS IS）提供，**不提供任何明示或默示的担保**，包括但不限于适销性、特定用途适用性、非侵权性。作者**不承诺**持续更新、修复缺陷或提供技术支持；外部应用（大众点评/百度地图等）流程可能因第三方变更而失效，需自行维护。

5. **使用责任**：使用者应遵守所在国家/地区的法律法规，并遵守所用应用、模拟器、框架的**用户协议**与**服务条款**。

6. **第三方内容**：本仓库通过 `git submodule` 引用的 `assets/MaaCommonAssets`、`third_party/QQReadScript` 等属第三方资源，其版权归各自作者；本仓库不转载、不分发受版权保护的程序本体（如 `MaaQQReaderGUI.exe` 之外的第三方运行时），仅提供开发与部署指引。

7. **禁止用途**：严禁将本项目用于任何营利性运营、代练、批量养号、商业授权，或破坏应用公平性的场景。

**使用本项目即表示您已接受上述免责声明。**

---

## 鸣谢

- 本项目由 **[MaaFramework](https://github.com/MaaXYZ/MaaFramework)** 强力驱动。
- 基于 [MAA](https://github.com/MaaAssistantArknights/MaaAssistantArknights) 的自动化生态。
- OCR 资产来自 [MaaCommonAssets](https://github.com/MaaXYZ/MaaCommonAssets)。
