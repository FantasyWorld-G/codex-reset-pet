# Codex Reset Pet · 桌面重置小精灵

[![简体中文](https://img.shields.io/badge/%E8%AF%AD%E8%A8%80-%E7%AE%80%E4%BD%93%E4%B8%AD%E6%96%87-0969da?style=for-the-badge)](README.md)
[![English](https://img.shields.io/badge/Language-English-6e7781?style=for-the-badge)](README.en.md)

由于本人经常忘记重置的节点，导致很多重置都浪费了。然后搞了一个这个桌面插件。内置了tibo reset按钮(https://codex-reset.com/zh/tibo)，点击打开即可。

Windows 桌面常驻小精灵，显示 **Codex 账户额度重置** 与 **重置卡到期** 的北京时间、剩余时长，并提供 Tibo 消息查询插件。

<img src="docs/pet-preview.png" width="288" alt="睡眠状态渲染预览，头顶冒出逐渐变大的 zzz">

这是独立的本机桌面程序和 Codex 技能插件，不是 OpenAI 官方 Pets。支持 Windows 10/11；桌面程序无需 API Key。账户同步需要已登录、可提供账户状态工具的 Codex 桌面端。

## 通过 Codex 安装（优先入口）

当前版本 **v0.4.8**，完整包内置当前 9 段语气音。下载发布包并解压后，双击 **install.cmd** 即可安装/升级并启动；也可使用下面的 Codex 安装方式。

首次安装，在 **PowerShell 或 Codex 的 PowerShell 终端**依次执行两步。

**1. 安装配套插件**（已安装可跳过）：

```powershell
codex plugin marketplace add FantasyWorld-G/codex-reset-pet --ref v0.4.8
codex plugin add reset-reminder@codex-reset-pet
```

**2. 安装桌面小精灵并自动启动：**

```powershell
$file = "$env:TEMP\codex-reset-pet-install.ps1"
Invoke-WebRequest -UseBasicParsing 'https://raw.githubusercontent.com/FantasyWorld-G/codex-reset-pet/v0.4.8/install.ps1' -OutFile $file
powershell -NoProfile -ExecutionPolicy Bypass -File $file -SkipPlugin
```

完成后小精灵会自动出现，并创建桌面快捷方式。首次安装需要联网，会准备 Python/Pillow；默认安装到 `%LOCALAPPDATA%\CodexResetPet`。`-SkipPlugin` 只避免重复注册插件，不影响桌面启动。

**只想安装桌面小精灵？直接执行第 2 步。** 仅需聊天插件则只执行第 1 步。桌面额度刷新需要已登录的 Codex CLI。[Codex 插件命令依据](https://learn.chatgpt.com/docs/cli/reference)。

## 再次启动与检查版本

安装后重新打开终端，只需：

```powershell
codex-pet
```

也可以双击桌面的 **Codex Reset Pet** 快捷方式。启动不调用 AI、不消耗模型额度，已运行时不会重复打开。

| 命令 | 用途 |
| --- | --- |
| `codex-pet` | 启动 |
| `codex-pet status` | 查看是否运行 |
| `codex-pet version` | 查看安装版本 |
| `codex-pet help` | 查看命令帮助 |
| `codex-pet sounds` | 查看音效来源、位置与运行时静音状态 |

提示找不到命令时，完全退出并重新打开终端应用；Codex 内置终端可能需要重启 Codex。退出小精灵请使用人物右键菜单。

## 一键更新（已安装用户）

在 PowerShell 执行；安装器会正常关闭旧实例，再启动新版：

```powershell
$file = "$env:TEMP\codex-reset-pet-update.ps1"
Invoke-WebRequest -UseBasicParsing 'https://raw.githubusercontent.com/FantasyWorld-G/codex-reset-pet/main/update.ps1' -OutFile $file
powershell -NoProfile -ExecutionPolicy Bypass -File $file
```

自动安装最新稳定版并启动，保留账户快照、设置和个人音效。以后仍使用这组命令，无需手动改版本号。只安装桌面的用户在最后一行加 `-SkipPlugin`；自定义目录加 `-InstallRoot '原安装目录'`。

## 内置新版语气音

**完整安装包已包含当前 9 段语气音，安装或升级后直接使用，无需复制文件或执行导入命令。** 旧版自动发现的个人音效文件会保留，但不会遮盖新版默认音效；静音偏好不变。`codex-pet sounds` 显示 `amitaro-bundled` 时就是内置新版。

需要主动使用自己的音效时，才使用可选的 `codex-pet sounds "音效文件夹"`。[音效对应关系与署名](docs/voice-credits.md)。

## 第一次同步账户

在新的 Codex 聊天中发送：

> 使用 reset-reminder 插件，同步我的账户额度重置和重置卡到期信息到桌面小精灵，只同步一次，不创建定时任务。

**额度自动刷新默认开启**：启动时读取一次，之后每 5 分钟自动读取本机已登录 Codex 的额度，也可随时点击 **刷新**。无需开启自动用卡。断网或读取失败时保留旧数据，按 30/60/120/240/300 秒重试；恢复后回到每 5 分钟。右键可关闭自动刷新，选择会保存。重置卡到期明细可能仍需完整同步。安装不会创建 Codex 定时任务或开机自启。

## 日常操作

| 操作 | 效果 |
| --- | --- |
| 单击人物 | 展开/收起气泡；每第三次单击鼓脸 |
| 双击人物 | 摸摸头和轻笑，不切换气泡 |
| 拖动、松手 | 移动人物和落地动作；拖远 180 像素触发一次开心音 |
| 10 秒不操作 | 持续睡眠，头顶出现 zzz；触碰唤醒 |
| 右键人物 | 表情互动、开关音效、额度自动刷新、临期用卡设置、退出 |
| 刷新 / 更新预估 | 分别更新账户额度 / Tibo 网站信息 |

气泡显示额度、重置卡到期、Tibo 预估和上次重置。时间均为北京时间，并随临近程度变色。网站预估不代表本账户已经重置。临期自动用卡默认关闭，需主动开启；电脑休眠或断网时无法保证执行。

## 其他安装方式与说明

| 需求 | 说明 |
| --- | --- |
| 手动 ZIP 下载、SHA-256 校验 | [手动安装](docs/installation.md#手动下载发布包无需-git) |
| Git / 源码安装 | [源码安装](docs/installation.md#git--源码安装) |
| 自定义目录、`-NoLaunch`、`-NoPath` 等 | [安装与更新参数](docs/installation.md#安装与更新参数) |
| 仅更新 Codex 插件 | [插件更新](docs/installation.md#仅更新-codex-插件) |
| 同步、自动用卡、卸载、故障排查 | [完整使用说明](docs/使用说明.md) |
| 开发测试 / 版本变化 | [开发命令](docs/installation.md#开发与测试) · [版本记录](CHANGELOG.md) |

## 音效署名


内置语气音的声音来自 **あみたろの声素材工房（Amitaro’s Voice Material Studio）**：[作者网站](https://amitaro.net/)。感谢作者提供录音素材。录音遵循[作者使用条款](https://amitaro.net/voice/voice_rule/)，不属于本项目源码许可。录音仅作为完整应用的资源内置，不作为独立素材包发布；使用和再分发须遵守作者条款。原合成音仅作损坏时的回退。详细文件对应关系见[语气音与署名说明](docs/voice-credits.md)。
