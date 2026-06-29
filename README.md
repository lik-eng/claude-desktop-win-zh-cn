# Claude Desktop Windows 中文补丁

为 **Windows 版 Claude Desktop** 添加简体中文界面的本地补丁。

> ⚠️ 本项目**非 Anthropic 官方**，是个人维护的本地化补丁。它修改本机已安装的 Claude
> 程序文件；所有改动均会先备份、可一键还原。译文复用并致谢开源项目
> [`Jyy1529/claude-desktop_win-zh_cn`](https://github.com/Jyy1529/claude-desktop_win-zh_cn)。

适配版本：**Claude Desktop `1.15200.0.0`（Microsoft Store / WindowsApps 版）**。
其它相近版本通常也能用（脚本按“特征匹配”定位，不写死文件 hash），且已在 1.14271 →
1.15200 的自动更新中验证过这套定位逻辑仍然有效，但不保证每个版本都成。

---

## 它做了什么

| 改动 | 位置 |
|------|------|
| 写入中文前端译文（约 1.6 万条键，~98% 已译、其余回退英文） | `app\resources\ion-dist\i18n\zh-CN.json` |
| 写入中文桌面外壳译文（菜单、托盘、对话框，>99%） | `app\resources\zh-CN.json` |
| 写入中文模型/思考选择器译文（46 条，100%） | `app\resources\ion-dist\i18n\dynamic\zh-CN.json` |
| 把 `zh-CN` 加入语言白名单，让“中文（简体）”出现在语言列表 | 前端 chunk 内的语言数组 |
| 注入“可见文本修复运行时”，把 i18n 漏掉的硬编码英文运行时替换为中文 | 前端入口 chunk |
| 设置默认语言为 `zh-CN` | `%APPDATA%\Claude-3p\config.json`、`%APPDATA%\Claude\config.json` |

> 说明：其余约 1.5%（约 260 余条）前端文案为品牌/产品名（如 Claude API、
> Amazon Bedrock）、占位符/符号格式串、或极复杂嵌套 ICU，会**按设计保留英文**
> 以保证不破坏占位符替换、不误译专有名词，不影响功能。

---

## 环境要求

- Windows 10/11
- 已安装 Claude Desktop（Store 版或 web 登录安装版）
- **Python 3**（[下载](https://www.python.org/downloads/)，安装时勾选 *Add to PATH*）
- **管理员权限**（WindowsApps 目录受系统保护，安装/卸载需要）
- 仓库已预生成含中文的 `resources/*.json`，**克隆即可装、无需联网**；
  只有当你想重新从上游对齐刷新译文时才需联网（`build_translations.py`，缓存到 `resources\_cache`）

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
（用仓库已预生成的译文，无需联网）关闭 Claude → 备份原文件 → 接管权限并应用补丁。

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

菜单选择 **`[3]`**：一次只读的智能体检，报告（不会改任何文件、也不需要管理员）：

- 三个 `zh-CN.json` 译文文件是否就位、各自**中文覆盖率**；
- 语言白名单是否已含 `zh-CN`、可见文本修复运行时是否已注入；
- **版本漂移检测**：比对当初被备份的 chunk 文件名与当前安装，若被备份的 chunk
  已不在当前安装目录，说明 Claude 已更新到新版本、**补丁已失效**，会提示你重装。

等价命令：`python scripts\patch_install.py --status`

---

## ⚠️ Claude 更新后需要重新安装

Claude Desktop 自动更新后，程序目录会换成新版本号、前端 chunk 的文件名（hash）也会变，
**补丁会失效**。更新后请**再次运行安装**（菜单 `[1]`）即可。

想确认是否已失效：跑菜单 `[3]` 状态，看到“版本漂移检测”那段提示“chunk 已不存在、
请重装”，就说明需要重跑安装（参见上文「查看状态」）。

---

## 单独使用各脚本（进阶）

```powershell
# 仅生成/刷新译文（联网；产物在 resources\）
python scripts\build_translations.py
python scripts\build_translations.py --offline   # 用缓存，不联网

# 仅打补丁（需管理员）
python scripts\patch_install.py
python scripts\patch_install.py --dry-run        # 只校验定位，不改文件
python scripts\patch_install.py --status          # 智能状态体检（只读，不需管理员）
python scripts\patch_install.py --no-runtime     # 不注入可见文本修复运行时

# 仅还原（需管理员）
python scripts\restore.py
python scripts\restore.py --reset-locale         # 同时清除 locale

# 用 Claude API 机翻补齐仍回退英文的键（进阶；需 ANTHROPIC_API_KEY 或第三方中转）
python scripts\translate_fallback.py --base-url https://api.example.com --key-file key.txt
python scripts\translate_fallback.py --merge     # 把缓存的机翻补丁合并回 resources/*.json（带占位符+garble 双校验）

# 指定安装目录（自动探测失败时）
python scripts\patch_install.py --root "C:\Program Files\WindowsApps\Claude_x.x.x.x_x64__xxxx"
```

---

## 目录结构

```
.
├── README.md
├── LICENSE / THIRD-PARTY-NOTICES.md
├── claude-zh-cn.ps1          # 交互菜单（自动提权）
├── install.ps1 / uninstall.ps1
├── scripts/
│   ├── common.py             # 安装路径探测 + JS 特征定位 + 备份/权限工具
│   ├── build_translations.py # 拉取并对齐译文，生成 resources/*.json
│   ├── patch_install.py      # 拷贝译文 / 改白名单 / 注入运行时 / 设 locale / --status 体检
│   ├── restore.py            # 还原与清理
│   └── translate_fallback.py # 用 Claude API 重新机翻回退键（进阶）
├── runtime/
│   └── visible-text-fix.js   # 可见文本修复运行时（MutationObserver）
├── resources/                # 译文产物（已预生成含中文，克隆即可用）
│   ├── frontend-zh-CN.json
│   ├── desktop-zh-CN.json
│   └── dynamic-zh-CN.json
└── .github/
    ├── workflows/lint.yml        # CI：校验 JSON/Python/.ps1/运行时标记
    └── ISSUE_TEMPLATE/, pull_request_template.md
```

备份目录：`%LOCALAPPDATA%\Claude-zh-CN-backup`（卸载时据此还原）。

---

## 常见问题

**Q：语言列表里没有“中文（简体”）？**
A：确认安装步骤里“白名单文件”一行有正常输出；重启 Claude。若版本过新导致定位失败，
请在 issue 里附上你的版本号。

**Q：界面大部分中文，但仍有少量英文？**
A：分两种：① 品牌/产品名（Claude API、Amazon Bedrock 等）、占位符/符号格式串、
极复杂嵌套 ICU 会**按设计保留英文**（保证不破坏占位符、不误译专有名词），属正常；
② i18n 没走、硬编码在 JS 里的文案——可见文本修复运行时会处理常见的那些，如仍有遗漏
可在 `runtime\visible-text-fix.js` 的 `EXACT` 映射表里补充后重装。

**Q：某个图标不见了 / 点击没反应？**
A：可见文本修复运行时**只改可见文本、不改内部标识**，正常不会导致此问题。若出现，
请先 `[2]` 卸载确认是否本补丁所致，并反馈。

**Q：运行 .ps1 报“无法加载，因为在此系统上禁止运行脚本”？**
A：用本文档给的带 `-ExecutionPolicy Bypass` 的命令运行即可。若是**下载的 ZIP** 解压后被
Windows 标记为“来自 Internet”而拦截，在项目文件夹的 PowerShell 里跑一次：
`Get-ChildItem -Recurse | Unblock-File`，再重新安装。

**Q：会被 Claude 更新覆盖吗？**
A：会。每次更新后重跑安装即可。用菜单 `[3]` 状态里的“版本漂移检测”可确认是否已失效。

---

## 贡献

- 反馈 bug / 提需求：开 [issue](https://github.com/lik-eng/claude-desktop-win-zh-cn/issues/new/choose)，按模板填（附版本号、`[3]` 状态输出最好）。
- 提 PR：仓库有 [PR 模板](.github/pull_request_template.md)，含改动类型勾选与自测清单。
- CI（[`.github/workflows/lint.yml`](.github/workflows/lint.yml)）会对每个 PR/push 自动跑：
  译文 JSON 合法且键不重复、全部 Python `py_compile`、`.ps1` 用 pwsh 解析且确认带 UTF-8 BOM、运行时 JS 的 BEGIN/END 标记 + 哨兵 + 纯 LF —— 任一失败 CI 即红。

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
