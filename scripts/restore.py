#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
restore.py — 卸载中文补丁，恢复官方原状。

需要管理员权限。

步骤：
  1. 从 %LOCALAPPDATA%\\Claude-zh-CN-backup 按相对路径还原被修改的 JS。
  2. 删除 3 个 zh-CN.json（前端 i18n / 外壳 / dynamic）。
  3. 兜底清理（即便备份缺失也尽量复原）：
       - 从当前白名单 chunk 的 KH 数组移除 ,"zh-CN"
       - 从入口 chunk 移除哨兵包裹的注入块
  4. 可选：清除 config.json 的 locale（默认保留，加 --reset-locale 才清）。

用法：
  python scripts/restore.py [--root <安装包根目录>] [--reset-locale]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402


def restore_from_backup(paths: common.Paths) -> int:
    """把备份目录里的文件按相对路径还原回 resources。返回还原的文件数。"""
    backup_res = common.BACKUP_ROOT / "resources"
    if not backup_res.exists():
        common.warn("未找到备份目录，跳过备份还原，改用兜底清理。")
        return 0
    n = 0
    for bf in backup_res.rglob("*"):
        if not bf.is_file():
            continue
        rel = bf.relative_to(backup_res)
        dst = paths.resources / rel
        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(bf.read_bytes())
            common.ok(f"已还原 {rel}")
            n += 1
        except Exception as e:
            common.warn(f"还原 {rel} 失败：{e}")
    return n


def delete_zh_files(paths: common.Paths) -> None:
    for f in (paths.frontend_zh, paths.shell_zh, paths.dynamic_zh):
        try:
            if f.exists():
                f.unlink()
                common.ok(f"已删除 {f.name}（{f.parent.name}）")
        except Exception as e:
            common.warn(f"删除 {f} 失败：{e}")


def fallback_clean_whitelist(paths: common.Paths) -> None:
    """若白名单仍含 zh-CN，移除之。"""
    found = common.find_whitelist_file(paths)
    if not found:
        # 也可能备份已还原成功，数组里本就没有 zh-CN
        return
    js, array_text = found
    if '"zh-CN"' not in array_text:
        return
    cleaned = array_text.replace(',"zh-CN"', "").replace('"zh-CN",', "").replace('"zh-CN"', "")
    text = common.read_js(js)
    text = text.replace(array_text, cleaned, 1)
    common.write_js(js, text)
    common.ok(f"已从白名单移除 zh-CN（{js.name}）")


def fallback_clean_runtime(paths: common.Paths) -> None:
    """从入口 chunk 移除哨兵包裹的注入块。"""
    entry = common.find_entry_chunk(paths)
    if not entry:
        return
    text = common.read_js(entry)
    if common.RUNTIME_BEGIN_MARK not in text:
        return
    # 移除 BEGIN..END 之间（含标记）的整段；容忍前面的 "\n;"
    pattern = re.compile(
        r"\n?;?\s*" + re.escape(common.RUNTIME_BEGIN_MARK)
        + r".*?" + re.escape(common.RUNTIME_END_MARK) + r"\s*",
        re.DOTALL,
    )
    new_text, count = pattern.subn("", text)
    if count:
        common.write_js(entry, new_text)
        common.ok(f"已移除注入运行时（{entry.name}）")


def reset_locale() -> None:
    for cfg in common.CONFIG_FILES:
        try:
            if not cfg.exists():
                continue
            data = json.loads(cfg.read_text(encoding="utf-8-sig"))
            if "locale" in data:
                del data["locale"]
                cfg.write_text(json.dumps(data, ensure_ascii=False, indent=4), encoding="utf-8")
                common.ok(f"已清除 {cfg.parent.name}\\config.json 的 locale")
        except Exception as e:
            common.warn(f"处理 {cfg} 失败：{e}")


def main() -> int:
    ap = argparse.ArgumentParser(description="卸载 Claude Desktop 中文补丁")
    ap.add_argument("--root", help="Claude 安装包根目录（默认自动探测）")
    ap.add_argument("--reset-locale", action="store_true", help="同时清除 config.json 的 locale 设置")
    args = ap.parse_args()

    print("== 卸载 Claude Desktop 中文补丁 ==")

    if not common.is_admin():
        common.err("需要管理员权限才能修改 WindowsApps 目录。")
        return 13

    try:
        root = common.find_install_root(args.root)
    except RuntimeError as e:
        common.err(str(e))
        return 2
    paths = common.Paths(root)
    common.info(f"安装目录：{root}")

    # 1) 优先用备份还原 JS
    restore_from_backup(paths)
    # 2) 删除 zh-CN 译文文件
    delete_zh_files(paths)
    # 3) 兜底：确保白名单/运行时已干净（备份缺失或还原不全时生效）
    fallback_clean_whitelist(paths)
    fallback_clean_runtime(paths)
    # 4) 可选清 locale
    if args.reset_locale:
        reset_locale()
    else:
        common.info("保留 config.json 的 locale（如需清除可加 --reset-locale）。")

    print()
    common.ok("卸载完成！请完全退出并重启 Claude Desktop。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
