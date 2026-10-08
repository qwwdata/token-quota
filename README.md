# Token Quota

**Windows 极简透明 Codex 额度电池条。**

**A minimal, transparent Codex quota battery for Windows.**

[简体中文](#chinese) · [English](#english)

![电池条预览 / Battery preview](docs/battery.png)

<a id="chinese"></a>

## 简体中文

Token Quota 将 Codex 的剩余额度显示为一个手机状态栏风格的悬浮电池。只有 **64 × 28 像素**，圆角、透明背景、无标题、无常驻文字。可放在桌面宠物下方，也可独立使用。

### 功能与操作

- 默认显示 **5 小时剩余额度**。填充随剩余额度变化，随 Windows 明暗主题使用黑色或白色；低于或等于 20% 时变红。
- **右键**切换「5 小时 / 每周」，查看准确百分比和重置时间，或立即刷新、退出。
- **左键拖动**电池移动位置，位置会自动保存。每次普通启动都默认回到 5 小时。
- 使用真正的逐像素透明窗口，背景不遮挡桌面，透明区域不拦截点击。
- 接收 `account/rateLimits/updated` 通知后立即更新；同时每 **10 秒**主动读取作为补充。其他 Codex 会话的消耗可能要等上游返回新数据后才能显示。
- 无数据时显示提示点；连接异常或数据超过 30 秒未更新时变灰并显示提示点。灰色填充为上次数据，右键可查看状态。真实 0% 是无提示点的空电池。

### 安装（Windows 10 / 11）

需要 Python **3.10+**、Pillow，以及已使用 **ChatGPT 账号登录**的 Codex 桌面应用或 Codex CLI。API Key 的按量计费没有对应的 5 小时 / 每周额度，可能显示「暂不可用」。

1. [下载 ZIP](https://github.com/qwwdata/token-quota/archive/refs/heads/main.zip) 并解压，或 `git clone https://github.com/qwwdata/token-quota.git`。
2. 在该目录打开 PowerShell，运行：

   ```powershell
   powershell -NoProfile -ExecutionPolicy Bypass -File .\setup.ps1
   ```

   已有 Python 环境可明确指定，不依赖 `py` 启动器：

   ```powershell
   powershell -NoProfile -ExecutionPolicy Bypass -File .\setup.ps1 -Python 'C:\path\to\python.exe'
   ```

3. 双击 `start.cmd`。首次把电池拖到合适的位置即可。

启动器优先使用项目 `.venv`，没有固定任何作者本机路径。若 Pillow 已安装，也可直接运行：

```powershell
& 'C:\path\to\pythonw.exe' -X utf8 .\token_quota.py
```

程序从 PATH 或 `%LOCALAPPDATA%\OpenAI\Codex\bin` 自动查找 CLI；也可在当前终端通过 `$env:CODEX_CLI = 'C:\path\to\codex.exe'` 指定。

命令行可选项：`--mode week` 以周额度启动，`--interval 10` 设置补充轮询秒数（最小 5 秒）。

### 随 Codex 自动打开（可选）

安装完成后，在项目目录运行一次：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\install_autostart.ps1
```

这会创建当前用户的 Windows 计划任务 `TokenQuota-Codex`。后台检测器在登录时启动，每 2 秒检查一次 Codex 桌面应用；打开 Codex 后自动显示电池，退出 Codex 后关闭由检测器打开的电池。不会把 Codex CLI、额度查询子进程或独立的 ChatGPT 应用当作 Codex 桌面应用。在电池右键菜单选择退出后，该次 Codex 会话中不会反复拉起；下次重新打开 Codex 时再次显示。请保留安装目录。

关闭自动联动：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\uninstall_autostart.ps1
```

### 数据来源与隐私

读取官方 [Codex app-server](https://learn.chatgpt.com/docs/app-server) 的 `account/rateLimits/read`，展示 `100 - usedPercent`。按接口实际 `windowDurationMins` 识别 300 分钟和 10080 分钟窗口，不把缺失值当作零。只读取额度，不启动模型对话，不修改账户登录，不上传个人额度或凭据到本仓库。

窗口位置保存在 `%LOCALAPPDATA%\TokenQuota\position.json`；启用自动联动后，如检测器发生异常，会在同目录保存 `monitor.log` 错误信息。退出电池时关闭由本工具创建的 app-server 子进程。默认不启用登录自启；上述自动联动需要主动安装。不依赖 Pets 插件，也不会自动跟随宠物位置。

### 开发与验证

```powershell
.\.venv\Scripts\python.exe -X utf8 -m unittest discover -s tests -v
```

`battery.py` 负责抗锯齿 RGBA 图形，`token_quota.py` 使用 Windows `UpdateLayeredWindow` 显示逐像素透明窗口，`quota_client.py` 负责后台额度读取与重连。运行时没有 Tkinter、浏览器或网页服务器依赖。

MIT License。非官方工具，与 Apple 或 OpenAI 无关联。

[Back to English / 切换英文](#english)

---

<a id="english"></a>

## English

Token Quota displays your remaining Codex quota as a floating battery inspired by a phone's status bar. It measures just **64 × 28 pixels**, with rounded corners, a transparent background, no title bar, and no persistent text. Place it beneath a desktop pet or use it on its own.

### Features and controls

- Shows your **remaining 5-hour quota** by default. The fill follows the remaining percentage, uses black or white to match the Windows light or dark theme, and turns red at 20% or below.
- **Right-click** to switch between **5 hours** (`5 小时`) and **weekly** (`每周`), view the exact remaining percentage and reset time, refresh immediately, or quit.
- **Drag with the left mouse button** to move the battery. Its position is saved automatically. Each normal launch starts with the 5-hour window.
- Uses true per-pixel transparency. The background does not cover your desktop, and fully transparent areas let mouse clicks pass through.
- Updates immediately when an `account/rateLimits/updated` notification arrives, with a quota read every **10 seconds** as a fallback. Usage from other Codex sessions appears once the upstream service returns updated data.
- A small indicator appears when no data is available. Connection errors or data older than 30 seconds make the battery gray and show the indicator. Gray fill represents the last known value; right-click to check its status. An actual 0% quota is an empty battery without the indicator.

### Installation (Windows 10 / 11)

Requires **Python 3.10+**, Pillow, and the Codex desktop app or Codex CLI signed in with a **ChatGPT account**. API-key billing does not provide the corresponding 5-hour or weekly quotas, so these windows may appear as unavailable.

1. [Download the ZIP](https://github.com/qwwdata/token-quota/archive/refs/heads/main.zip) and extract it, or run `git clone https://github.com/qwwdata/token-quota.git`.
2. Open PowerShell in the project directory and run:

   ```powershell
   powershell -NoProfile -ExecutionPolicy Bypass -File .\setup.ps1
   ```

   To use an existing Python installation, specify its path explicitly. The `py` launcher is not required:

   ```powershell
   powershell -NoProfile -ExecutionPolicy Bypass -File .\setup.ps1 -Python 'C:\path\to\python.exe'
   ```

3. Double-click `start.cmd`, then drag the battery to your preferred position.

The launcher prefers the project's `.venv` and contains no hard-coded paths from the author's computer. If Pillow is already installed, you can also launch it directly:

```powershell
& 'C:\path\to\pythonw.exe' -X utf8 .\token_quota.py
```

The app finds the CLI through PATH or `%LOCALAPPDATA%\OpenAI\Codex\bin`. To specify a CLI executable in the current terminal, use `$env:CODEX_CLI = 'C:\path\to\codex.exe'`.

Optional arguments: `--mode week` starts with the weekly quota; `--interval 10` sets the fallback polling interval in seconds, with a minimum of 5 seconds.

### Open automatically with Codex (optional)

After installation, run this once from the project directory:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\install_autostart.ps1
```

This creates the current user's Windows scheduled task, `TokenQuota-Codex`. A background monitor starts at sign-in and checks for the Codex desktop app every 2 seconds. It opens the battery when Codex starts and closes the battery it opened when Codex exits. It excludes the Codex CLI, quota-reader subprocesses, and the separate ChatGPT app. If you quit the battery from its context menu, it stays closed for that Codex session and returns the next time Codex starts. Keep the installation directory in place.

To disable this behavior:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\uninstall_autostart.ps1
```

### Data source and privacy

The app calls `account/rateLimits/read` through the official [Codex app-server](https://learn.chatgpt.com/docs/app-server) and displays `100 - usedPercent`. It identifies the 300-minute and 10,080-minute windows from the actual `windowDurationMins` values. Missing data is never treated as zero. It only reads quota metadata: it does not start model conversations, change your account login, or upload your personal quota or credentials to this repository.

The window position is saved in `%LOCALAPPDATA%\TokenQuota\position.json`. If the optional monitor encounters an error, it writes `monitor.log` in the same directory. On exit, the battery closes the app-server process it created. Startup at sign-in is disabled by default and requires installing the optional integration above. The app does not require the Pets plugin or automatically follow a pet's position.

### Development and testing

```powershell
.\.venv\Scripts\python.exe -X utf8 -m unittest discover -s tests -v
```

`battery.py` renders antialiased RGBA graphics, `token_quota.py` uses Windows `UpdateLayeredWindow` for per-pixel transparency, and `quota_client.py` handles background quota reads and reconnection. There is no runtime dependency on Tkinter, a browser, or a web server.

Released under the MIT License. This is an unofficial tool and is not affiliated with Apple or OpenAI.

[返回中文 / Back to Chinese](#chinese)
