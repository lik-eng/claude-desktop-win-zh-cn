#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
validate_placeholders.py — 校验并修复译文占位符完整性。

对 frontend / desktop 译文，逐键比较"该键的英文原文"与"zh 译文"的占位符
明文集合。任何不一致 → 该键回退为英文（绝不写坏 ICU / HTML / 变量名）。

占位符明文集合包含：
  - 所有 {...} 片段（含 ICU 嵌套的外层；用括号配平提取，保留内层变量名）
  - 所有 <tag> / </tag>
  - 复数锚 #  的"出现次数"也算（锚被挪位会改变语义）

用法：
  python scripts/validate_placeholders.py          # 只报告，不改文件
  python scripts/validate_placeholders.py --fix    # 回退不一致键为英文
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

PROJECT = Path(__file__).resolve().parent.parent
PAIRS = [
    ("frontend", PROJECT / "resources" / "frontend-zh-CN.json"),
    ("desktop", PROJECT / "resources" / "desktop-zh-CN.json"),
]


def _balanced_braces(s: str) -> set[str]:
    """提取所有顶层 {...}（括号配平，含嵌套整段作为单个占位符明文）。"""
    out = set()
    depth = 0
    start = None
    for i, c in enumerate(s):
        if c == "{":
            if depth == 0:
                start = i
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0 and start is not None:
                out.add(s[start : i + 1])
                start = None
    return out


def _tags(s: str) -> set[str]:
    return set(re.findall(r"</?[a-zA-Z][^>]*?>", s))


def _hash_count(s: str) -> int:
    # ICU 复数锚 # 的出现次数（挪位会改变语义/数量）
    return s.count("#")


def signature(s: str) -> tuple:
    return (frozenset(_balanced_braces(s)), frozenset(_tags(s)), _hash_count(s))


def main() -> int:
    ap = argparse.ArgumentParser(description="校验/修复译文占位符")
    ap.add_argument("--fix", action="store_true", help="不一致键回退为英文")
    args = ap.parse_args()

    import os
    root = common.find_install_root()
    p = common.Paths(root)
    en_paths = {"frontend": p.frontend_en, "desktop": p.shell_en}

    total_bad = 0
    fixed = 0
    for name, zh_path in PAIRS:
        en = json.load(open(en_paths[name], encoding="utf-8"))
        zh = json.load(open(zh_path, encoding="utf-8"))
        bad_keys = []
        for k, ev in en.items():
            zv = zh.get(k, "")
            if not isinstance(ev, str) or not isinstance(zv, str):
                continue
            if signature(ev) != signature(zv):
                bad_keys.append(k)
        total_bad += len(bad_keys)
        common.info(f"{name}: 占位符不一致 {len(bad_keys)} 条")
        if args.fix and bad_keys:
            for k in bad_keys:
                zh[k] = en[k]  # 回退英文
                fixed += 1
            zh_path.write_text(
                json.dumps(zh, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            common.ok(f"{name}: 已回退 {len(bad_keys)} 条为英文")
    if args.fix:
        common.ok(f"完成，共回退 {fixed} 条。")
    else:
        common.info(f"合计不一致 {total_bad} 条；加 --fix 回退为英文。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())