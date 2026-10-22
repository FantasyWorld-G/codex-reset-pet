# Codex Reset Pet · 桌面重置小精灵

[![简体中文](https://img.shields.io/badge/%E8%AF%AD%E8%A8%80-%E7%AE%80%E4%BD%93%E4%B8%AD%E6%96%87-0969da?style=for-the-badge)](README.md)
[![English](https://img.shields.io/badge/Language-English-6e7781?style=for-the-badge)](README.en.md)

由于本人经常忘记重置的节点，导致很多重置都浪费了。然后搞了一个这个桌面插件。内置了tibo reset按钮(https://codex-reset.com/zh/tibo)，点击打开即可。

Windows 桌面常驻小精灵，显示 **Codex 账户额度重置** 与 **重置卡到期** 的北京时间、剩余时长，并提供 Tibo 消息查询插件。

<img src="docs/pet-preview.png" width="288" alt="睡眠状态渲染预览，头顶冒出逐渐变大的 zzz">

这是独立的本机桌面程序和 Codex 技能插件，不是 OpenAI 官方 Pets。支持 Windows 10/11；桌面程序无需 API Key。账户同步需要已登录、可提供账户状态工具的 Codex 桌面端。

## 一键安装

在 **PowerShell** 中复制运行下面这一行（固定安装 v0.4.2）：

下文功能以 `main` 分支源码为准；v0.4.2 安装包不包含后续新增的剩余额度进度条和手动刷新按钮。需要最新功能时，请使用下方的源码安装方式。

```powershell
$f = Join-Path $env:TEMP 'codex-reset-pet-install.ps1'; Invoke-WebRequest -UseBasicParsing 'https://raw.githubusercontent.com/FantasyWorld-G/codex-reset-pet/v0.4.2/install.ps1' -OutFile $f; powershell -NoProfile -ExecutionPolicy Bypass -File $f
```

安装脚本会下载发布包并核对 SHA-256，检测 Python，必要时通过 winget 安装当前用户的 Python 3.12，在独立虚拟环境安装 Pillow，创建桌面快捷方式，然后启动小精灵。检测到 Codex CLI 时，也会安装配套插件。无需 Git；通常无需管理员权限。首次运行需要连接 GitHub、PyPI；缺少 Python 时还需要 winget 软件源。

安装位置：`%LOCALAPPDATA%\CodexResetPet`。不会自动建立定时任务或开机自启，也不会读取你的登录凭证。可先查看 [安装脚本](install.ps1)，或从 [Release](https://github.com/FantasyWorld-G/codex-reset-pet/releases/tag/v0.4.2) 手动下载。

## 第一次使用

安装后，在 **新的 Codex 聊天** 中发送：

> 使用 reset-reminder 插件，把我的账户额度重置和重置卡到期信息同步到已安装的桌面小精灵，只同步一次，不创建定时任务。

首次同步之前，窗口显示“等待账户同步”，不会带入发布者的账户信息。最新源码版也可点击“刷新”，通过已登录的 Codex CLI 获取额度和重置时间；重置卡到期明细仍需完整账户同步。

想自动同步时，再单独告诉 Codex：

> 每小时同步一次桌面小精灵的账户状态，同时检查 Tibo 重置消息；只有需要提醒时通知我。

以后可说“关闭重置提醒的定时任务”。自动检查依赖电脑开机、Codex 运行及可用网络和额度，并非独立后台账户服务。

## 使用方式

| 操作 | 效果 |
| --- | --- |
| 点击人物 | 挥手/眨眼，同时展开或收起气泡；每第三次点击鼓脸 |
| 拖拽人物 | 移动窗口，显示惊讶和倾斜动作 |
| 松开拖拽 | 开心弹跳，再回到待机 |
| 10 秒无互动 | 直接进入并持续保持睡眠，头顶循环冒出由小变大的 zzz |
| 睡眠时点击或拖动 | 唤醒并响应操作；按住期间不会入睡 |
| 点击“刷新” | 从已登录的 Codex CLI 获取最新额度和重置时间，过程中不阻塞动画 |
| 点击 `tibo reset` | 默认浏览器打开 [Tibo 页面](https://codex-reset.com/zh/tibo) |
| 点击气泡的 × | 只收起气泡 |
| 右键人物 → 退出桌面小精灵 | 退出程序 |

两项时间按剩余时间分别变色，人物保留原始配色。动画状态直接切换，不插入其他表情；目标刷新率 60Hz，实际表现取决于电脑负载。账户快照超过 90 分钟会显示“数据待同步”，不会把旧数据当成实时状态。

账户卡片还显示“剩余额度 XX%”和进度条，数值为 Codex 官方账户状态的 `100 - usedPercent`，随账户快照更新。无数据时显示 `--`，过期快照标记“上次同步”。窗口每 5 秒重读本地数据，每 0.5 秒重算倒计时，这两个操作不会请求账户。点击“刷新”才通过 Codex 的 `account/rateLimits/read` 接口获取最新额度，不开启定时任务，也不发起模型对话。刷新中禁止重复点击，失败会提示并保留上次数据。

手动刷新数据保存在独立的 `desktop-usage.json`，不覆盖插件的完整 `usage.json`。窗口选择时间较新的额度；当前 CLI 可能只返回重置卡数量，不含到期明细，此时卡片标记“上次记录”，需要完整账户同步才能更新卡到期信息。

## 其他安装方式

已有 Python 3.10+（含 tkinter）的用户可下载源码，运行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\install.ps1 -SourcePath .
```

仅安装 Codex 查询插件，不安装桌面程序：

```powershell
codex plugin marketplace add FantasyWorld-G/codex-reset-pet --ref v0.4.2
codex plugin add reset-reminder@codex-reset-pet
```

插件市场的安装方式见 [OpenAI 官方插件文档](https://developers.openai.com/plugins/build/plugins)。单独安装查询插件不会安装 Python/Pillow，也不会自动启动小精灵。

## 说明书和维护

- [完整说明书：数据同步、安装参数、更新、卸载及故障排查](docs/使用说明.md)
- [版本记录](CHANGELOG.md)
- [素材生成说明](plugins/reset-reminder/assets/生成说明.txt)

本仓库只包含程序、测试和角色素材，不包含账户快照、凭证、日志或个人定时任务。社区消息分为预告、待核实、社区确认和储备重置；社区确认不等于本人账户已到账。不会自动使用重置卡。

## 开发与测试

```powershell
python -m pip install -r requirements.txt
python -m unittest discover -s plugins/reset-reminder/tests -v
python scripts/build_release.py
```

40 项测试覆盖状态机、倒计时、重置卡筛选、消息去重和 Windows 原生拖拽回归。非 Windows 环境会跳过原生窗口集成测试。发布包和校验文件生成在 `dist/`，构建使用明确的文件列表，排除运行数据和缓存。
