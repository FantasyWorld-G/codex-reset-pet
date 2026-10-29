# 其他安装与更新方式

[返回首页](../README.md) · [English](installation.en.md)

以下方式按需选择，不需要全部执行。日常启动只需 `codex-pet`。


### 手动下载发布包（无需 Git）

从 [v0.4.6 Release](https://github.com/FantasyWorld-G/codex-reset-pet/releases/tag/v0.4.6) 下载 `codex-reset-pet-v0.4.6.zip` 和 `SHA256SUMS.txt`。将两者放在同一目录，运行下面的校验命令；仅在校验通过后解压，并在解压后的 `codex-reset-pet` 目录运行安装器。

```powershell
$archive = (Resolve-Path '.\codex-reset-pet-v0.4.6.zip').Path
$expected = ((Get-Content '.\SHA256SUMS.txt' | Where-Object { $_ -match '\s+codex-reset-pet-v0\.4\.6\.zip$' }) -split '\s+')[0]
$sha256 = [Security.Cryptography.SHA256]::Create()
$archiveStream = [IO.File]::OpenRead($archive)
try { $actual = ([BitConverter]::ToString($sha256.ComputeHash($archiveStream))).Replace('-','') }
finally { $archiveStream.Dispose(); $sha256.Dispose() }
if ($actual -ne $expected) { throw 'SHA-256 mismatch' }
```

在解压后的目录中：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\install.ps1 -SourcePath .
```

### Git / 源码安装

需要已安装 Git。在准备保存源码的目录运行：

```powershell
git clone --branch v0.4.6 --depth 1 https://github.com/FantasyWorld-G/codex-reset-pet.git
Set-Location codex-reset-pet
powershell -NoProfile -ExecutionPolicy Bypass -File .\install.ps1 -SourcePath .
```

也可从 GitHub 下载源码 ZIP，解压后运行同一条 `install.ps1 -SourcePath .` 命令。安装器仍会检查 Python 和安装 Pillow，需要相应网络连接。

### 仅安装桌面程序 / 自定义目录

以下为解压后的发布包或源码目录中的替代命令，按需选择一条：

```powershell
# 仅安装桌面程序，跳过 Codex 插件注册
powershell -NoProfile -ExecutionPolicy Bypass -File .\install.ps1 -SourcePath . -SkipPlugin

# 安装到指定目录
powershell -NoProfile -ExecutionPolicy Bypass -File .\install.ps1 -SourcePath . -InstallRoot 'D:\Apps\CodexResetPet'

# 安装但暂不启动，也不创建桌面快捷方式
powershell -NoProfile -ExecutionPolicy Bypass -File .\install.ps1 -SourcePath . -NoLaunch -NoShortcut
```

仅安装桌面程序仍需已登录的 Codex CLI 才能使用额度刷新。完整参数见 [使用说明](使用说明.md)。

## 安装与更新参数

参数追加在 `powershell ... -File $file` 命令末尾。除 `-SourcePath` 仅用于安装器，其余参数也适用于更新器。

| 参数 | 用途 |
| --- | --- |
| `-InstallRoot 'D:\Apps\CodexResetPet'` | 自定义目录；更新时与原安装目录一致 |
| `-SkipPlugin` | 跳过插件注册，仍安装并启动桌面程序 |
| `-NoLaunch` | 完成后暂不启动 |
| `-NoShortcut` | 不创建桌面快捷方式 |
| `-NoPath` | 不修改用户 PATH，仍创建命令文件 |
| `-SourcePath .` | 从当前解压后的源码目录安装 |

## 不通过 PATH 启动

默认安装位置可使用以下命令；自定义安装请替换目录：

```powershell
& "$env:LOCALAPPDATA\CodexResetPet\bin\codex-pet.cmd"
```

提示找不到 `codex-pet` 时，完全关闭并重新打开终端应用；内置终端可能需要重启宿主应用。

## 仅更新 Codex 插件


适用于按首页命令添加的 Git 市场。将固定版本切换到 v0.4.6：

```powershell
codex plugin marketplace remove codex-reset-pet
codex plugin marketplace add FantasyWorld-G/codex-reset-pet --ref v0.4.6
codex plugin add reset-reminder@codex-reset-pet
```

以后升级时将 `v0.4.6` 替换为已发布的新标签。若你的 Git 市场明确跟踪 `main`，可改用下面两条；固定标签执行 `upgrade` 不会自动跳到新版本：

```powershell
codex plugin marketplace upgrade codex-reset-pet
codex plugin add reset-reminder@codex-reset-pet
```

如果由桌面安装器注册的是本地市场，请使用[首页的桌面更新命令](../README.md#一键更新已安装用户)。仅更新插件不会升级桌面文件；完成后新建 Codex 聊天。[官方市场命令说明](https://learn.chatgpt.com/docs/cli/reference)。

## 开发与测试

```powershell
python -m pip install -r requirements.txt
python -m unittest discover -s plugins/reset-reminder/tests -v
python scripts/build_release.py
```

回归测试覆盖状态机、倒计时、重置卡筛选、消息去重、断网重连、超时取消、异常响应、保存失败、Tibo 预估解析及 Windows 原生窗口布局和刷新回归。非 Windows 环境会跳过原生窗口集成测试。详见 [异常处理测试记录](异常处理测试.md)。发布包和校验文件生成在 `dist/`，构建使用明确的文件列表，排除运行数据和缓存。


## 个人音效

所有安装方式默认提供合成音，更新保留已有个人音效。桌面 v0.4.6 起可运行 `codex-pet sounds` 查看或 `codex-pet sounds "音效文件夹"` 导入；[跨设备步骤与原素材列表](voice-credits.md#安装与跨设备迁移--install-and-transfer)。仅更新聊天插件不会迁移桌面音效。
