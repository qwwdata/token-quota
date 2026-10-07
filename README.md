# Token Quota

Windows 上的极简 Codex 额度悬浮电池条。参考手机状态栏的电池形状，只有 **64 × 28 像素**，圆角、透明背景、无标题、无常驻文字。可放在桌面宠物下方，也可独立使用。

![真实额度电池预览](docs/battery.png)

## 使用

- 默认显示 **5 小时剩余额度**。填充随剩余额度变化，随 Windows 明暗主题使用黑色或白色；低于或等于 20% 时变红。
- **右键**切换「5 小时 / 每周」，查看准确百分比和重置时间，或立即刷新、退出。
- **左键拖动**电池移动位置，位置会自动保存。每次普通启动都默认回到 5 小时。
- 使用真正的逐像素透明窗口，背景不遮挡桌面，透明区域不拦截点击。
- 接收 `account/rateLimits/updated` 通知后立即更新；同时每 **10 秒**主动读取作为补充。其他 Codex 会话的消耗可能要等上游返回新数据后才能显示。
- 无数据时显示提示点；连接异常或数据超过 30 秒未更新时变灰并显示提示点。灰色填充为上次数据，右键可查看状态。真实 0% 是无提示点的空电池。

## 安装（Windows 10 / 11）

需要 Python **3.10+**、Pillow，以及已使用 **ChatGPT 账号登录**的 Codex 桌面应用或 Codex CLI。API Key 的按量计费没有对应的 5 小时 / 每周额度，可能显示「暂不可用」。

1. 下载本仓库 ZIP 并解压，或 `git clone https://github.com/qwwdata/token-quota.git`。
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

## 数据来源与隐私

读取官方 [Codex app-server](https://learn.chatgpt.com/docs/app-server) 的 `account/rateLimits/read`，展示 `100 - usedPercent`。按接口实际 `windowDurationMins` 识别 300 分钟和 10080 分钟窗口，不把缺失值当作零。只读取额度，不启动模型对话，不修改账户登录，不上传个人额度或凭据到本仓库。

仅在 `%LOCALAPPDATA%\TokenQuota\position.json` 保存窗口位置。退出时关闭由本工具创建的 app-server 子进程。没有开机自启，不依赖 Pets 插件，也不会自动跟随宠物位置。

## 开发与验证

```powershell
.\.venv\Scripts\python.exe -X utf8 -m unittest discover -s tests -v
```

`battery.py` 负责抗锯齿 RGBA 图形，`token_quota.py` 使用 Windows `UpdateLayeredWindow` 显示逐像素透明窗口，`quota_client.py` 负责后台额度读取与重连。运行时没有 Tkinter、浏览器或网页服务器依赖。

MIT License。非官方工具，与 Apple 或 OpenAI 无关联。
