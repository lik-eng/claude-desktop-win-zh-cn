#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
common.py — Claude Desktop 中文补丁的公共工具函数。

负责：
  - 自动探测 Claude Desktop 的安装目录（Store / WindowsApps 版优先）
  - 解析各关键资源文件路径
  - 备份目录、config.json 路径
  - 在 minified JS 中用“特征匹配”定位语言白名单数组与入口 chunk（不写死 hash）

被 build_translations.py / patch_install.py / restore.py 复用。
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

# ----------------------------------------------------------------------------
# 常量
# ----------------------------------------------------------------------------

# 参考开源项目（译文来源），默认分支为 master（不是 main）
REF_REPO_RAW = "https://raw.githubusercontent.com/Jyy1529/claude-desktop_win-zh_cn/master"

# 备份根目录：%LOCALAPPDATA%\Claude-zh-CN-backup
BACKUP_ROOT = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData/Local"))) / "Claude-zh-CN-backup"

# locale 配置文件（两个 deployment 模式都覆盖）
CONFIG_FILES = [
    Path(os.environ.get("APPDATA", str(Path.home() / "AppData/Roaming"))) / "Claude-3p" / "config.json",
    Path(os.environ.get("APPDATA", str(Path.home() / "AppData/Roaming"))) / "Claude" / "config.json",
]

TARGET_LOCALE = "zh-CN"

# 官方语言序列（用于在 JS 中定位 KH 白名单数组）。本版实测为这 11 个。
OFFICIAL_LOCALES = [
    "en-US", "de-DE", "fr-FR", "ko-KR", "ja-JP",
    "es-419", "es-ES", "it-IT", "hi-IN", "pt-BR", "id-ID",
]

# 注入运行时的防重复哨兵
RUNTIME_SENTINEL = "__CLAUDE_ZH_CN_VTF__"
RUNTIME_BEGIN_MARK = "/*== CLAUDE_ZH_CN_VTF_BEGIN ==*/"
RUNTIME_END_MARK = "/*== CLAUDE_ZH_CN_VTF_END ==*/"


# ----------------------------------------------------------------------------
# 安装路径探测
# ----------------------------------------------------------------------------

def _appx_install_location() -> Path | None:
    """用 PowerShell 的 Get-AppxPackage 拿到 Store 版安装目录。"""
    try:
        out = subprocess.run(
            [
                "powershell.exe", "-NoProfile", "-Command",
                "(Get-AppxPackage -Name '*claude*' | "
                "Sort-Object Version -Descending | "
                "Select-Object -First 1).InstallLocation",
            ],
            capture_output=True, text=True, timeout=30,
        )
        loc = out.stdout.strip()
        if loc and Path(loc).exists():
            return Path(loc)
    except Exception:
        pass
    return None


def _scan_windowsapps() -> Path | None:
    """回退：扫描 WindowsApps，取版本号最大、且含 app\\resources\\en-US.json 的目录。"""
    base = Path(r"C:\Program Files\WindowsApps")
    candidates: list[tuple[tuple[int, ...], Path]] = []
    try:
        for entry in base.glob("Claude_*_x64__*"):
            if (entry / "app" / "resources" / "en-US.json").exists():
                m = re.search(r"Claude_([0-9.]+)_", entry.name)
                ver = tuple(int(x) for x in m.group(1).split(".")) if m else (0,)
                candidates.append((ver, entry))
    except Exception:
        pass
    if candidates:
        candidates.sort(key=lambda t: t[0], reverse=True)
        return candidates[0][1]
    return None


def _localappdata_anthropic() -> Path | None:
    """回退：web-login 安装版 %LOCALAPPDATA%\\AnthropicClaude\\app-*。"""
    base = Path(os.environ.get("LOCALAPPDATA", "")) / "AnthropicClaude"
    if not base.exists():
        return None
    # web 版结构通常是 AnthropicClaude\app-<ver>\resources
    apps = sorted(base.glob("app-*"), reverse=True)
    for app in apps:
        if (app / "resources").exists():
            # 把 InstallLocation 抽象成“含 app\resources 的根”；这里 app 本身即根
            return app.parent  # 让 app_root() 统一处理
    return None


def find_install_root(manual: str | None = None) -> Path:
    """
    返回 Claude 安装的“包根目录”（即含 `app\\resources` 的上层）。

    优先级：手动指定 > Get-AppxPackage > WindowsApps 扫描 > LOCALAPPDATA\\AnthropicClaude。
    找不到则抛 RuntimeError。
    """
    if manual:
        p = Path(manual)
        if not p.exists():
            raise RuntimeError(f"手动指定的路径不存在：{p}")
        return p

    for finder in (_appx_install_location, _scan_windowsapps, _localappdata_anthropic):
        root = finder()
        if root:
            return root

    raise RuntimeError(
        "未能自动找到 Claude Desktop 安装目录。\n"
        "请确认已安装 Claude Desktop；或用 --root 手动指定包根目录"
        "（即包含 app\\resources\\en-US.json 的那一层）。"
    )


def app_resources_dir(install_root: Path) -> Path:
    """
    从包根定位到 resources 目录。兼容两种结构：
      Store:  <root>\\app\\resources
      web:    <root>\\app-<ver>\\resources  或  <root>\\resources
    """
    candidates = [
        install_root / "app" / "resources",
        install_root / "resources",
    ]
    for c in candidates:
        if (c / "en-US.json").exists():
            return c
    # web 版：root 下找 app-* / resources
    for app in sorted(install_root.glob("app-*"), reverse=True):
        c = app / "resources"
        if (c / "en-US.json").exists():
            return c
    raise RuntimeError(f"在 {install_root} 下未找到 resources（缺 en-US.json）。")


class Paths:
    """集中所有关键路径，供各脚本取用。"""

    def __init__(self, install_root: Path):
        self.install_root = install_root
        self.resources = app_resources_dir(install_root)
        self.i18n = self.resources / "ion-dist" / "i18n"
        self.i18n_dynamic = self.i18n / "dynamic"
        self.assets = self.resources / "ion-dist" / "assets"

        # 英文基准
        self.shell_en = self.resources / "en-US.json"
        self.frontend_en = self.i18n / "en-US.json"
        self.dynamic_en = self.i18n_dynamic / "en-US.json"

        # zh-CN 目标
        self.shell_zh = self.resources / f"{TARGET_LOCALE}.json"
        self.frontend_zh = self.i18n / f"{TARGET_LOCALE}.json"
        self.dynamic_zh = self.i18n_dynamic / f"{TARGET_LOCALE}.json"

    def asset_js_files(self) -> list[Path]:
        """所有前端 JS chunk（递归 assets，含 v1/ 等版本子目录）。"""
        return sorted(self.assets.rglob("*.js"))


# ----------------------------------------------------------------------------
# JS 特征匹配：语言白名单数组 & 入口 chunk
# ----------------------------------------------------------------------------

# 匹配形如  ["en-US","de-DE",...,"id-ID"]  的官方语言数组。
# 用 en-US 开头 + 含全部官方语言来唯一定位，避免误伤。
# 结尾允许在 "id-ID" 之后再跟若干额外语言（如已注入的 "zh-CN"），
# 这样打补丁前后都能找到同一个数组（幂等检测 + 卸载兜底都依赖它）。
_WHITELIST_RE = re.compile(
    r'\[\s*"en-US"'
    + "".join(r'\s*,\s*"' + re.escape(loc) + r'"' for loc in OFFICIAL_LOCALES[1:])
    + r'(?:\s*,\s*"[A-Za-z0-9-]+")*'  # 可选的额外语言（如 zh-CN）
    + r'\s*\]'
)


def find_whitelist_file(paths: "Paths") -> tuple[Path, str] | None:
    """
    在 assets 的 JS 里找到包含官方语言白名单数组的文件。
    返回 (文件路径, 匹配到的数组原文)；找不到返回 None。
    """
    for js in paths.asset_js_files():
        try:
            text = read_js(js)
        except Exception:
            continue
        m = _WHITELIST_RE.search(text)
        if m:
            return js, m.group(0)
    return None


def find_entry_chunk(paths: "Paths") -> Path | None:
    """
    定位前端入口 chunk：含 i18n 加载逻辑（fetch `/i18n/${...}.json`）的那个文件。
    用于追加注入可见文本修复运行时。优先 index-*.js。
    """
    needle_re = re.compile(r"/i18n/\$\{")
    # 先在 index-*.js 里找
    index_files = sorted(paths.assets.rglob("index-*.js"))
    others = [p for p in paths.asset_js_files() if p not in index_files]
    for js in index_files + others:
        try:
            text = read_js(js)
        except Exception:
            continue
        if needle_re.search(text):
            return js
    return None


# ----------------------------------------------------------------------------
# JSON / 备份 小工具
# ----------------------------------------------------------------------------

def read_js(path: Path) -> str:
    """读取 JS chunk 文本，不做换行转换（保留原始 LF/CRLF）。"""
    return path.read_bytes().decode("utf-8", errors="ignore")


def write_js(path: Path, text: str) -> None:
    """写回 JS chunk，按 UTF-8 字节写入，不让 Python 改动换行符。

    这样修改 minified chunk 时只改我们打算改的字节，文件其余部分逐字节不变，
    便于卸载时核对/还原，也避免把 LF 全转成 CRLF 导致体积变化。
    """
    path.write_bytes(text.encode("utf-8"))


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def dump_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def backup_path_for(paths: "Paths", target: Path) -> Path:
    """把安装目录内某文件映射到备份目录下的镜像路径（按相对 resources 的相对路径）。"""
    rel = target.relative_to(paths.resources)
    return BACKUP_ROOT / "resources" / rel


def backup_file(paths: "Paths", target: Path) -> Path | None:
    """首次备份 target（已存在备份则跳过）。返回备份路径；target 不存在则返回 None。"""
    if not target.exists():
        return None
    dest = backup_path_for(paths, target)
    if dest.exists():
        return dest  # 已备份，保持最初的官方版本
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(target.read_bytes())
    return dest


def is_admin() -> bool:
    """是否管理员（Windows）。"""
    try:
        import ctypes
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def _run_quiet(cmd: list[str]) -> tuple[int, str]:
    """跑一个外部命令，吞掉输出，返回 (returncode, 合并的 stdout+stderr)。"""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        return r.returncode, (r.stdout or "") + (r.stderr or "")
    except Exception as e:  # noqa: BLE001
        return 1, str(e)


def grant_write_access(target: Path) -> bool:
    """
    让当前管理员对 target（文件或目录）可写。

    WindowsApps 下的文件归 TrustedInstaller 所有，光提权到管理员也只有读权限、
    不能写。这里用 takeown 接管所有权 + icacls 给 Administrators 组 (F) 完全控制；
    若是目录则递归（/r /d y、(OI)(CI)）。成功返回 True。

    幂等：重复授予不会报错。失败不抛异常，仅返回 False，由调用方决定是否兜底。
    """
    if not target.exists():
        # 文件还不存在（要新建）——对其父目录授权即可
        target = target.parent
    is_dir = target.is_dir()
    path = str(target)

    if is_dir:
        rc1, _ = _run_quiet(["takeown.exe", "/f", path, "/r", "/d", "y"])
        rc2, _ = _run_quiet(["icacls.exe", path, "/grant", "*S-1-5-32-544:(OI)(CI)F", "/t", "/c", "/q"])
    else:
        rc1, _ = _run_quiet(["takeown.exe", "/f", path])
        rc2, _ = _run_quiet(["icacls.exe", path, "/grant", "*S-1-5-32-544:F", "/c", "/q"])
    # icacls 成功（rc2==0）即认为可写；takeown 偶尔对个别子项返回非 0 但不影响目标
    return rc2 == 0


def info(msg: str) -> None:
    print(f"  {msg}")


def ok(msg: str) -> None:
    print(f"  [OK] {msg}")


def warn(msg: str) -> None:
    print(f"  [!] {msg}")


def err(msg: str) -> None:
    print(f"  [X] {msg}", file=sys.stderr)
