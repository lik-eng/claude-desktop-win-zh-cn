#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
translate_fallback.py — 用 Anthropic Claude API 把 frontend / desktop 译文里
仍为英文的回退键批量翻成中文。

安全设计：
  - 只取“当前值不含 CJK”的回退键去翻译；已含中文的键不动。
  - 占位符逐字保护：译前取 ICU `{...}`、HTML `<tag>`、`#` 锚的快照，
    译后集合必须一致；不一致则该键回退英文（绝不写坏 ICU）。
  - 术语表（Artifact=工件、Project=项目…）随系统提示注入，统一用语。
  - 断点续跑：译文补丁缓存到 resources/_work/zh_patch.json，已译键跳过；
    中断后重跑从断点继续。
  - 分批：一批 N 条，逐批请求、逐批写盘；单批失败不影响已落盘的。

用法：
  set ANTHROPIC_API_KEY=...   或   key 文件见 --key-file
  python scripts/translate_fallback.py
  python scripts/translate_fallback.py --model claude-haiku-4-5-20251001
  python scripts/translate_fallback.py --check   # 只校验已缓存补丁，不联网
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent
WORK = PROJECT / "resources" / "_work"
PATCH_FILE = WORK / "zh_patch.json"
TARGETS = {
    "frontend": PROJECT / "resources" / "frontend-zh-CN.json",
    "desktop": PROJECT / "resources" / "desktop-zh-CN.json",
}

DEFAULT_MODEL = "claude-haiku-4-5-20251001"
BATCH_SIZE = 60  # 每批翻译条数

GLOSSARY = [
    ("Artifact", "工件"), ("Artifacts", "工件"), ("Live artifacts", "实时工件"),
    ("Project", "项目"), ("Projects", "项目"), ("Connector", "连接器"),
    ("Settings", "设置"), ("Workspace", "工作区"), ("Seat", "席位"),
    ("Usage credit", "用量额度"), ("Spend limit", "消费限额"),
    ("Claude Code", "Claude Code"), ("Skill", "技能"), ("Agent", "智能体"),
    ("MCP", "MCP"), ("Connector", "连接器"), ("Routine", "例程"),
    ("Webhook", "Webhook"), ("SAML", "SAML"), ("SCIM", "SCIM"),
]

SYSTEM_PROMPT = (
    "你是一名软件界面本地化翻译，把英文 UI 文案翻成简体中文。规则：\n"
    "1. 只输出翻译后文本，不要解释、不要引号、不要前后空格。\n"
    "2. 占位符逐字保留，绝不改动、不翻译、不增删：ICU 语法如 "
    "`{count, plural, one {# message} other {# messages}}` 只翻译大括号"
    "里的英文短语（# 锚和外壳一字不动）；`{name}`、`<tag>`、`</tag>` 原样保留。\n"
    "3. 专业术语遵循术语表。代码、URL、文件路径、API 名、产品名保持英文。\n"
    "4. 保持语气与正式度，简洁，符合中文 UI 习惯。\n"
    "5. 输入是 JSON 对象 {id: 英文}，你输出同结构的 JSON {id: 中文}，"
    "id 一字不变，缺的 id 也要原样保留并填中文。\n"
    f"术语表：{json.dumps(GLOSSARY, ensure_ascii=False)}"
)


def _has_cjk(s: str) -> bool:
    return isinstance(s, str) and any("一" <= c <= "鿿" for c in s)


def _placeholders(s: str) -> set:
    ph = set(re.findall(r"\{[^{}]*\}", s))
    ph |= set(re.findall(r"</?[a-zA-Z][^>]*?>", s))
    if "#" in s:
        ph.add("#")
    return ph


def load_patch() -> dict:
    if PATCH_FILE.exists():
        return json.loads(PATCH_FILE.read_text(encoding="utf-8"))
    return {}


def save_patch(p: dict) -> None:
    WORK.mkdir(parents=True, exist_ok=True)
    PATCH_FILE.write_text(
        json.dumps(p, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def collect_pending() -> dict:
    """收集所有回退键 {uniq_value: [keys...]}；只保留补丁里还没译好的 value。"""
    patch = load_patch()
    by_value: dict[str, list[str]] = {}
    for fname, target in TARGETS.items():
        data = json.loads(target.read_text(encoding="utf-8"))
        for k, v in data.items():
            if not isinstance(v, str) or _has_cjk(v):
                continue
            if v in patch and _has_cjk(patch[v]):
                continue  # 已有译文，跳过
            by_value.setdefault(v, []).append(k)  # 同英文复用一条译文
    return by_value


def call_api(client, model: str, batch: dict[str, str]) -> dict[str, str]:
    """调一次 Messages API，把 {id: english} 翻成 {id: chinese}。"""
    prompt = (
        "把下面 JSON 的每个 value 翻成简体中文，占位符与 id 保持不变，"
        "只输出结果 JSON：\n" + json.dumps(batch, ensure_ascii=False)
    )
    msg = client.messages.create(
        model=model,
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
    # 解析返回的 JSON（容错：剥掉前后可能的 ```/说明文字）
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


def merge_patch() -> int:
    """把 zh_patch.json（按英文原文键）合并回 frontend/desktop 译文 JSON，落盘。"""
    if not PATCH_FILE.exists():
        common.err("补丁文件不存在，先跑翻译。")
        return 2
    patch = load_patch()
    print(f"== 合并补丁到译文（补丁 {sum(1 for s in patch.values() if _has_cjk(s))} 条）==")
    for fname, target in TARGETS.items():
        data = json.loads(target.read_text(encoding="utf-8"))
        hit = rej = miss = 0
        for k, v in data.items():
            if not isinstance(v, str) or _has_cjk(v):
                continue
            zh = patch.get(v)
            if not zh or not _has_cjk(zh):
                miss += 1
                continue
            if _placeholders(v) != _placeholders(zh):
                rej += 1
                common.warn(f"占位符不一致，跳过：{k}")
                continue
            data[k] = zh
            hit += 1
        target.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        common.info(f"{fname}: 写入 {hit} | 拒绝 {rej} | 未覆盖 {miss}")
    common.ok("合并完成。")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="用 Claude API 批量翻译回退英文键")
    ap.add_argument("--model", default=DEFAULT_MODEL, help=f"模型，默认 {DEFAULT_MODEL}")
    ap.add_argument("--check", action="store_true", help="只校验补丁，不联网")
    ap.add_argument("--key-file", help="从文件读 API key（utf-8，单行）")
    ap.add_argument("--limit", type=int, help="只翻译前 N 条（调试用）")
    ap.add_argument("--merge", action="store_true", help="把补丁合并回译文 JSON（最终落盘）")
    ap.add_argument("--base-url", help="API base_url（第三方中转，如 https://api.shengadai.top）")
    args = ap.parse_args()

    if args.merge:
        return merge_patch()

    print("== 批量翻译回退键 ==")
    pending = collect_pending()
    common.info(f"待译 unique 英文：{len(pending)}")

    patch = load_patch()

    if args.check or not pending:
        # 仅校验已缓存补丁的占位符一致性
        bad = 0
        for fname, target in TARGETS.items():
            data = json.loads(target.read_text(encoding="utf-8"))
            for k, v in data.items():
                if k in patch and _has_cjk(patch[k]) and not _has_cjk(v):
                    if _placeholders(v) != _placeholders(patch[k]):
                        bad += 1
        common.ok(f"补丁键数：{sum(1 for s in patch.values() if _has_cjk(s))} | 占位符不一致：{bad}")
        return 0

    # 取 key
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if args.key_file:
        key = Path(args.key_file).read_text(encoding="utf-8-sig").strip()
    if not key:
        common.err("未找到 ANTHROPIC_API_KEY。设置环境变量，或用 --key-file <path>。")
        return 2

    import anthropic
    kw = {"api_key": key}
    if args.base_url:
        kw["base_url"] = args.base_url.rstrip("/")  # SDK 自己拼 /v1/messages
        # 第三方中转：清掉环境里的 gateway 变量，避免 SDK 优先读它
        os.environ.pop("ANTHROPIC_BASE_URL", None)
        os.environ.pop("ANTHROPIC_AUTH_TOKEN", None)
    client = anthropic.Anthropic(**kw)

    items = list(pending.items())
    if args.limit:
        items = items[: args.limit]

    total = len(items)
    done = 0
    rejected = 0
    for i in range(0, total, BATCH_SIZE):
        batch_items = items[i : i + BATCH_SIZE]
        batch = {f"t{j}": en for j, (en, _) in enumerate(batch_items)}
        try:
            resp = call_api(client, args.model, batch)
        except Exception as e:
            common.warn(f"第 {i}-{i+len(batch_items)} 批请求失败：{e}（跳过，稍后重跑）")
            time.sleep(2)
            continue
        for j, (en, keys) in enumerate(batch_items):
            zh = resp.get(f"t{j}")
            if not zh or not _has_cjk(zh):
                continue
            if _placeholders(en) != _placeholders(zh):
                rejected += 1
                continue
            patch[en] = zh  # 按英文原文 key 存，复用
            done += 1
        save_patch(patch)
        common.info(f"进度 {min(i+len(batch_items),total)}/{total} | 本批已落盘 | 累计译 {done} | 拒绝 {rejected}")
        time.sleep(0.5)

    common.ok(f"完成。累计译 {done} 条，占位符拒绝 {rejected} 条。补丁：{PATCH_FILE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())