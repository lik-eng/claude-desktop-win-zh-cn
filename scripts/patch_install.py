#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
patch_install.py — 把中文补丁应用到已安装的 Claude Desktop。

需要管理员权限（WindowsApps 目录受系统保护）。

步骤：
  1. 探测安装目录，校验 resources/*.json 译文已生成。
  2. 备份将被修改/覆盖的原文件到 %LOCALAPPDATA%\\Claude-zh-CN-backup。
  3. 拷贝 3 个 zh-CN.json 到对应位置。
  4. 在白名单 chunk 的 KH 数组里追加 "zh-CN"（精确定位，幂等）。
  5. 把可见文本修复运行时（带哨兵 IIFE）追加注入到入口 chunk（幂等）。
  6. 写入两个 config.json 的 locale=zh-CN（合并，不破坏其它字段）。

用法：
  python scripts/patch_install.py [--root <安装包根目录>] [--dry-run] [--no-runtime]

  --dry-run    只探测与校验，报告将要做什么，不写任何文件。
  --no-runtime 不注入可见文本修复运行时（仅做 JSON + 白名单）。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent
RES = PROJECT / "resources"
RUNTIME_JS = PROJECT / "runtime" / "visible-text-fix.js"


def ensure_resources() -> bool:
    needed = ["frontend-zh-CN.json", "desktop-zh-CN.json", "dynamic-zh-CN.json"]
    missing = [f for f in needed if not (RES / f).exists()]
    if missing:
        common.err(f"缺少译文文件：{missing}")
        common.err("请先运行：python scripts/build_translations.py")
        return False
    return True


def patch_whitelist(paths: common.Paths, dry: bool) -> bool:
    """在 KH 数组中追加 ,"zh-CN"。返回是否成功（已是中文也算成功）。"""
    found = common.find_whitelist_file(paths)
    if not found:
        common.err("未能在前端 JS 中定位语言白名单数组（KH）。")
        common.err("可能 Claude 版本结构有变，请反馈此版本号。")
        return False
    js, array_text = found
    common.info(f"白名单文件：{js.name}")

    if '"zh-CN"' in array_text:
        common.ok("白名单已包含 zh-CN，跳过。")
        return True

    new_array = array_text[:-1] + ',"zh-CN"]'  # 在结尾 ] 前插入
    if dry:
        common.info(f"[dry-run] 将把白名单改为 …,\"id-ID\",\"zh-CN\"]")
        return True

    common.backup_file(paths, js)
    text = common.read_js(js)
    # 只替换这一处（白名单数组是唯一匹配）
    text = text.replace(array_text, new_array, 1)
    common.write_js(js, text)
    common.ok("已把 zh-CN 加入语言白名单。")
    return True


def inject_runtime(paths: common.Paths, dry: bool) -> bool:
    entry = common.find_entry_chunk(paths)
    if not entry:
        common.err("未能定位入口 chunk（含 i18n 加载逻辑），跳过运行时注入。")
        return False
    common.info(f"入口 chunk：{entry.name}")

    text = common.read_js(entry)
    if common.RUNTIME_SENTINEL in text or common.RUNTIME_BEGIN_MARK in text:
        common.ok("运行时已注入，跳过。")
        return True

    if dry:
        common.info("[dry-run] 将把可见文本修复运行时追加到入口 chunk 末尾。")
        return True

    runtime_code = common.read_js(RUNTIME_JS)
    common.backup_file(paths, entry)
    # 追加到末尾；用换行 + 分号兜底，避免与前一句粘连
    common.write_js(entry, text + "\n;" + runtime_code + "\n")
    common.ok("已注入可见文本修复运行时。")
    return True


def copy_translations(paths: common.Paths, dry: bool) -> None:
    mapping = [
        (RES / "frontend-zh-CN.json", paths.frontend_zh),
        (RES / "desktop-zh-CN.json", paths.shell_zh),
        (RES / "dynamic-zh-CN.json", paths.dynamic_zh),
    ]
    for src, dst in mapping:
        if dry:
            common.info(f"[dry-run] 拷贝 {src.name} -> {dst}")
            continue
        # 目标若是官方文件（理论上 zh-CN 不存在官方版），仍做一次备份保险
        common.backup_file(paths, dst)
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(src.read_bytes())
        common.ok(f"已写入 {dst.name}")


def set_locale(dry: bool) -> None:
    for cfg in common.CONFIG_FILES:
        try:
            data = {}
            if cfg.exists():
                txt = cfg.read_text(encoding="utf-8-sig").strip()
                if txt:
                    data = json.loads(txt)
            if data.get("locale") == common.TARGET_LOCALE:
                common.ok(f"{cfg.parent.name}\\config.json 已是 zh-CN。")
                continue
            if dry:
                common.info(f"[dry-run] 设置 {cfg.parent.name}\\config.json locale=zh-CN")
                continue
            data["locale"] = common.TARGET_LOCALE
            cfg.parent.mkdir(parents=True, exist_ok=True)
            cfg.write_text(json.dumps(data, ensure_ascii=False, indent=4), encoding="utf-8")
            common.ok(f"已设置 {cfg.parent.name}\\config.json locale=zh-CN")
        except Exception as e:
            common.warn(f"写 {cfg} 失败：{e}")


def main() -> int:
    ap = argparse.ArgumentParser(description="应用 Claude Desktop 中文补丁")
    ap.add_argument("--root", help="Claude 安装包根目录（默认自动探测）")
    ap.add_argument("--dry-run", action="store_true", help="只校验，不写文件")
    ap.add_argument("--no-runtime", action="store_true", help="不注入可见文本修复运行时")
    args = ap.parse_args()

    print("== 安装 Claude Desktop 中文补丁 ==")

    if not args.dry_run and not common.is_admin():
        common.err("需要管理员权限才能修改 WindowsApps 目录。")
        common.err("请用管理员身份运行 claude-zh-cn.ps1，或在管理员 PowerShell 中执行。")
        return 13

    if not ensure_resources():
        return 2

    try:
        root = common.find_install_root(args.root)
    except RuntimeError as e:
        common.err(str(e))
        return 2
    paths = common.Paths(root)
    common.info(f"安装目录：{root}")
    common.info(f"备份目录：{common.BACKUP_ROOT}")

    # WindowsApps 下文件归 TrustedInstaller 所有，仅提权到管理员还不能写；
    # 先接管 resources 目录所有权并给 Administrators 完全控制，否则后续写入会
    # PermissionError。dry-run 不改 ACL。
    if not args.dry_run:
        if common.grant_write_access(paths.resources):
            common.ok("已获取 resources 目录写权限。")
        else:
            common.warn("获取写权限可能未完全成功，将继续尝试写入。")

    copy_translations(paths, args.dry_run)
    if not patch_whitelist(paths, args.dry_run):
        return 4
    if not args.no_runtime:
        inject_runtime(paths, args.dry_run)
    set_locale(args.dry_run)

    print()
    if args.dry_run:
        common.ok("dry-run 完成：路径与定位均正常，可正式安装。")
    else:
        common.ok("安装完成！请完全退出并重启 Claude Desktop。")
        common.info("若界面仍是英文：设置 → 语言 → 选择“中文（简体）”。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
