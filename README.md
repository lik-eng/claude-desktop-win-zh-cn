# Claude Desktop Windows 中文补丁

为 **Windows 版 Claude Desktop** 添加简体中文界面的本地补丁。

> ⚠️ 本项目**非 Anthropic 官方**，是个人维护的本地化补丁。它修改本机已安装的 Claude
> 程序文件；所有改动均会先备份、可一键还原。译文复用并致谢开源项目
> [`Jyy1529/claude-desktop_win-zh_cn`](https://github.com/Jyy1529/claude-desktop_win-zh_cn)。

适配版本：**Claude Desktop `1.14271.0.0`（Microsoft Store / WindowsApps 版）**。
其它相近版本通常也能用（脚本按“特征匹配”定位，不写死文件 hash），但不保证。

---

## 它做了什么

| 改动 | 位置 |
|------|------|
| 写入中文前端译文（约 1.6 万条键，~95% 已译、其余回退英文） | `app\resources\ion-dist\i18n\zh-CN.json` |
| 写入中文桌面外壳译文（菜单、托盘、对话框，~99%） | `app\resources\zh-CN.json` |
| 写入中文模型/思考选择器译文（46 条，100%） | `app\resources\ion-dist\i18n\dynamic\zh-CN.json` |
| 把 `zh-CN` 加入语言白名单，让“中文（简体）”出现在语言列表 | 前端 chunk 内的语言数组 |
| 注入“可见文本修复运行时”，把 i18n 漏掉的硬编码英文运行时替换为中文 | 前端入口 chunk |
| 设置默认语言为 `zh-CN` | `%APPDATA%\Claude-3p\config.json`、`%APPDATA%\Claude\config.json` |

> 说明：其余约半成（约 740 余条）前端文案因含复杂 ICU 复数/选择占位符或纯品牌名/URL，
> 会**回退显示英文**以保证不破坏占位符替换，不影响功能；后续可逐步精修。

---

## 环境要求

- Windows 10/11
- 已安装 Claude Desktop（Store 版或 web 登录安装版）
- **Python 3**（[下载](https://www.python.org/downloads/)，安装时勾选 *Add to PATH*）
- **管理员权限**（WindowsApps 目录受系统保护，安装/卸载需要）
- 安装译文时需联网（从参考仓库拉取译文，会缓存到 `resources\_cache`）

---

## 使用方法

### 第一步：获取项目

任选一种方式，下载到本机任意目录（路径无所谓，脚本按自身位置定位）：

- **用 git 克隆**

  ```powershell
  git clone https://github.com/lik-eng/claude-desktop-win-zh-cn.git
  cd claude-desktop-win-zh-cn
  ```

- **或下载 ZIP**：点本仓库右上角绿色 **Code → Download ZIP**，解压后进入该文件夹。

### 第二步：一键安装（推荐）

进入项目文件夹后，在 **普通 PowerShell** 里运行（脚本会自动请求管理员权限）：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\claude-zh-cn.ps1
```

然后在菜单选择 **`[1]` 安装 / 更新中文补丁**。脚本会自动：
生成译文（联网）→ 关闭 Claude → 备份原文件 → 接管权限并应用补丁。

> 也可直接双击 `claude-zh-cn.ps1` 运行。

完成后重新打开 Claude Desktop。若界面仍是英文：
**设置 → 语言 →“中文（简体）”**。

#### 想完全无人值守？（一条命令搞定）

在项目文件夹里粘贴下面这条，它会**直接安装并在装好后自动重启 Claude**（仍只弹一次提权框）。
命令使用当前所在目录，**不含任何写死的路径**，谁 clone 下来都能用：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\install.ps1; Start-Process "shell:AppsFolder\$((Get-StartApps | Where-Object { $_.Name -like '*Claude*' } | Select-Object -First 1).AppID)"
```

### 卸载（恢复官方原状）

菜单选择 **`[2]`**，或：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\uninstall.ps1
```

会从备份还原被改的文件、删除 zh-CN 译文、清理白名单与注入代码。
（默认保留 locale 设置；如需一并清除，运行
`python scripts\restore.py --reset-locale`。）

### 查看状态

菜单选择 **`[3]`**：显示探测到的安装目录、白名单文件、入口 chunk 等定位信息
（这其实是一次 `--dry-run`，不会改任何文件）。

---

## ⚠️ Claude 更新后需要重新安装

Claude Desktop 自动更新后，程序目录会换成新版本号、前端 chunk 的文件名（hash）也会变，
**补丁会失效**。更新后请**再次运行安装**（菜单 `[1]`）即可。

---

## 单独使用各脚本（进阶）

```powershell
# 仅生成/刷新译文（联网；产物在 resources\）
python scripts\build_translations.py
python scripts\build_translations.py --offline   # 用缓存，不联网

# 仅打补丁（需管理员）
python scripts\patch_install.py
python scripts\patch_install.py --dry-run        # 只校验定位，不改文件
python scripts\patch_install.py --no-runtime     # 不注入可见文本修复运行时

# 仅还原（需管理员）
python scripts\restore.py
python scripts\restore.py --reset-locale         # 同时清除 locale

# 指定安装目录（自动探测失败时）
python scripts\patch_install.py --root "C:\Program Files\WindowsApps\Claude_x.x.x.x_x64__xxxx"
```

---

## 目录结构

```
.
├── README.md
├── claude-zh-cn.ps1          # 交互菜单（自动提权）
├── install.ps1 / uninstall.ps1
├── scripts/
│   ├── common.py             # 安装路径探测 + JS 特征定位 + 备份工具
│   ├── build_translations.py # 拉取并对齐译文，生成 resources/*.json
│   ├── patch_install.py      # 拷贝译文 / 改白名单 / 注入运行时 / 设 locale
│   └── restore.py            # 还原与清理
├── runtime/
│   └── visible-text-fix.js   # 可见文本修复运行时（MutationObserver）
└── resources/                # 由 build_translations.py 生成
    ├── frontend-zh-CN.json
    ├── desktop-zh-CN.json
    └── dynamic-zh-CN.json
```

备份目录：`%LOCALAPPDATA%\Claude-zh-CN-backup`（卸载时据此还原）。

---

## 常见问题

**Q：语言列表里没有“中文（简体”）？**
A：确认安装步骤里“白名单文件”一行有正常输出；重启 Claude。若版本过新导致定位失败，
请在 issue 里附上你的版本号。

**Q：界面大部分中文，但仍有少量英文？**
A：分两种：① 含复杂 ICU 占位符或纯品牌名/URL 的少量键会**故意回退英文**
（保证占位符不被破坏、品牌名不误译），属正常；② i18n 没走、硬编码在 JS 里的
文案——可见文本修复运行时会处理常见的那些，如仍有遗漏可在
`runtime\visible-text-fix.js` 的 `EXACT` 映射表里补充后重装。

**Q：某个图标不见了 / 点击没反应？**
A：可见文本修复运行时**只改可见文本、不改内部标识**，正常不会导致此问题。若出现，
请先 `[2]` 卸载确认是否本补丁所致，并反馈。

**Q：运行 .ps1 报“无法加载，因为在此系统上禁止运行脚本”？**
A：用本文档给的带 `-ExecutionPolicy Bypass` 的命令运行即可。若是**下载的 ZIP** 解压后被
Windows 标记为“来自 Internet”而拦截，在项目文件夹的 PowerShell 里跑一次：
`Get-ChildItem -Recurse | Unblock-File`，再重新安装。

**Q：会被 Claude 更新覆盖吗？**
A：会。每次更新后重跑安装即可。

---

## 风险与免责

- 修改 WindowsApps 内的应用文件属第三方改动，非官方支持，理论上有随版本更新失效的风险。
- 本补丁所有写操作均先备份到 `%LOCALAPPDATA%\Claude-zh-CN-backup`，并提供一键还原。
- “Claude”“Claude Desktop” 是 Anthropic 的商标；本项目为非官方第三方本地化补丁，
  与 Anthropic 无隶属或背书关系。

---

## 许可

- 本项目代码与脚本以 **MIT** 许可发布，详见 [LICENSE](LICENSE)。
- 中文译文复用自上游 [`Jyy1529/claude-desktop_win-zh_cn`](https://github.com/Jyy1529/claude-desktop_win-zh_cn)（同为 MIT）。
  其许可与版权声明保留在 [THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md)，特此致谢。
