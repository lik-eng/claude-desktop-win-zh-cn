#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_translations.py — 生成中文译文资源。

流程：
  1. 从参考仓库（Jyy1529/claude-desktop_win-zh_cn @ master）拉取已译好的
     frontend-zh-CN.json / desktop-zh-CN.json。
  2. 读取本机安装版的英文基准（前端 / 外壳 / 动态）。
  3. 按安装版的键集对齐：参考仓库有该键就用其中文，否则回退英文。
  4. 动态选择器（模型/思考强度）这 46 条参考仓库未覆盖，用内置译表（按英文文案匹配）翻译。
  5. 写出 resources/{frontend,desktop,dynamic}-zh-CN.json，并打印覆盖率。

用法：
  python scripts/build_translations.py [--root <安装包根目录>] [--offline]

  --offline 时跳过联网，使用 resources/_cache 下已缓存的参考文件（若存在）。
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent
RES_OUT = PROJECT / "resources"
CACHE = RES_OUT / "_cache"

REF_FILES = {
    "frontend": f"{common.REF_REPO_RAW}/resources/frontend-zh-CN.json",
    "desktop": f"{common.REF_REPO_RAW}/resources/desktop-zh-CN.json",
}

# 动态选择器译表：按英文文案（去首尾空格）匹配。参考仓库不含这些键。
DYNAMIC_ZH = {
    "Complex, detailed work": "复杂、精细的工作",
    "Opus consumes usage limits faster than other models": "Opus 消耗用量额度的速度比其他模型更快",
    "Auto thinking": "自动思考",
    "Analysis tool": "分析工具",
    "Most efficient for everyday tasks": "处理日常任务最高效",
    "Best for math and coding challenges": "最适合数学与编程难题",
    "Extended": "扩展",
    "Web search": "网络搜索",
    "Always uses deep reasoning": "始终使用深度推理",
    "Adaptive": "自适应",
    "Adaptive thinking": "自适应思考",
    "Thinking": "思考",
    "Claude uses its access to the web to improve answers when appropriate.":
        "Claude 会在适当时联网以改进回答。",
    "Extra": "额外",
    "Included until June 22": "6 月 22 日前包含在内",
    "Most capable for ambitious work": "应对高难度工作最强",
    "Thinks for more complex tasks": "为更复杂的任务进行思考",
    "Upload CSVs for Claude to analyze quantitative data with high accuracy and create interactive data visualizations.":
        "上传 CSV，让 Claude 高精度分析定量数据并创建交互式数据可视化。",
    "Off": "关闭",
    "Light, casual tasks": "轻量、随意的任务",
    "Respond right away": "立即回复",
    "May use excessive tokens resulting in long response times and may hit token limits. Use sparingly for the hardest tasks.":
        "可能消耗过多 token，导致响应时间变长并可能触及 token 上限。请仅在最难的任务中谨慎使用。",
    "Medium": "中",
    "Default": "默认",
    "Low": "低",
    "For your toughest challenges": "应对你最棘手的挑战",
    "Max": "最高",
    "Balanced for everyday work": "兼顾日常工作的平衡选择",
    "Uses usage credits": "消耗用量额度",
    "Think longer for complex tasks": "为复杂任务思考更久",
    "Higher effort means more thorough responses, but takes longer and uses your limits faster.":
        "更高的努力程度意味着更周全的回答，但耗时更长，也会更快消耗你的额度。",
    "Match thinking to complexity": "根据复杂度匹配思考",
    "Can think for more complex tasks": "可为更复杂的任务进行思考",
    "Claude can search the internet to provide more up-to-date and relevant responses. Claude will automatically determine when to use web search if the topic requires current information. Web search is only available when using Claude 3.7 Sonnet.":
        "Claude 可以搜索互联网，以提供更及时、更相关的回答。当话题需要最新信息时，Claude 会自动判断何时使用网络搜索。网络搜索仅在使用 Claude 3.7 Sonnet 时可用。",
    "Org default": "组织默认",
    "Fastest for quick answers": "需要快速回答时最快",
    "The hardest problems. Takes longest.": "最难的问题，耗时最长。",
    "Claude can write and run code to process data, run analysis, and produce data visualizations in real time.":
        "Claude 可以编写并运行代码，实时处理数据、执行分析并生成数据可视化。",
    "Instant": "即时",
    "Extended thinking": "扩展思考",
    "Fable is included in your plan limits until June 22. After that, switch to usage credits to continue using it.":
        "在 6 月 22 日前，Fable 包含在你的套餐额度内。之后请切换为消耗用量额度以继续使用。",
    "High": "高",
    "Best for most use cases": "适合大多数使用场景",
    "Quick replies to simple questions": "快速回复简单问题",
}


def fetch_ref(name: str, url: str, offline: bool) -> dict:
    cache_file = CACHE / f"{name}-zh-CN.json"
    if offline:
        if cache_file.exists():
            common.info(f"[offline] 使用缓存 {cache_file.name}")
            return json.loads(cache_file.read_text(encoding="utf-8"))
        raise RuntimeError(f"--offline 但缺少缓存：{cache_file}")
    common.info(f"下载参考译文 {name} ...")
    req = urllib.request.Request(url, headers={"User-Agent": "claude-zh-cn-builder"})
    with urllib.request.urlopen(req, timeout=60) as r:
        raw = r.read().decode("utf-8")
    data = json.loads(raw)
    CACHE.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(raw, encoding="utf-8")
    return data


def _has_cjk(s: str) -> bool:
    return isinstance(s, str) and any("一" <= c <= "鿿" for c in s)


def align(installed_en: dict, ref_zh: dict) -> tuple[dict, int, int]:
    """
    按安装版的键集对齐：参考仓库有该键就用其中文，否则回退英文。

    返回 (结果, 含中文的数量, 回退英文的数量)。
    “含中文”按译文实际含 CJK 字符判定，与 README 引用的覆盖率口径一致
    （专有名词等参考值仍是英文的，计入回退，不虚高覆盖率）。
    """
    out: dict[str, str] = {}
    zh = fallback = 0
    for k, en in installed_en.items():
        val = ref_zh.get(k, en)
        out[k] = val
        if _has_cjk(val):
            zh += 1
        else:
            fallback += 1
    return out, zh, fallback


def build_dynamic(installed_en: dict) -> tuple[dict, int, int]:
    out: dict[str, str] = {}
    zh = fallback = 0
    for k, en in installed_en.items():
        val = DYNAMIC_ZH.get(en.strip(), en)
        out[k] = val
        if _has_cjk(val):
            zh += 1
        else:
            fallback += 1
    return out, zh, fallback


def main() -> int:
    ap = argparse.ArgumentParser(description="生成中文译文资源")
    ap.add_argument("--root", help="Claude 安装包根目录（默认自动探测）")
    ap.add_argument("--offline", action="store_true", help="跳过联网，使用缓存的参考译文")
    args = ap.parse_args()

    print("== 生成中文译文 ==")
    try:
        root = common.find_install_root(args.root)
    except RuntimeError as e:
        common.err(str(e))
        return 2
    paths = common.Paths(root)
    common.info(f"安装目录：{root}")

    # 英文基准
    fe_en = common.load_json(paths.frontend_en)
    sh_en = common.load_json(paths.shell_en)
    dy_en = common.load_json(paths.dynamic_en)

    # 参考译文
    try:
        ref_fe = fetch_ref("frontend", REF_FILES["frontend"], args.offline)
        ref_sh = fetch_ref("desktop", REF_FILES["desktop"], args.offline)
    except Exception as e:
        common.err(f"获取参考译文失败：{e}")
        common.err("可先联网运行一次以缓存，或检查网络/代理。")
        return 3

    RES_OUT.mkdir(parents=True, exist_ok=True)

    # 对齐
    fe_out, fe_t, fe_f = align(fe_en, ref_fe)
    sh_out, sh_t, sh_f = align(sh_en, ref_sh)
    dy_out, dy_t, dy_f = build_dynamic(dy_en)

    common.dump_json(RES_OUT / "frontend-zh-CN.json", fe_out)
    common.dump_json(RES_OUT / "desktop-zh-CN.json", sh_out)
    common.dump_json(RES_OUT / "dynamic-zh-CN.json", dy_out)

    # 覆盖率报告
    def pct(n, total):
        return f"{(100 * n / total):.1f}%" if total else "—"

    print("\n-- 覆盖率（含中文 / 共计）--")
    print(f"  前端 frontend : 共 {len(fe_en):>5} 键 | 中文 {fe_t:>5} ({pct(fe_t, len(fe_en))}) | 回退英文 {fe_f}")
    print(f"  外壳 desktop  : 共 {len(sh_en):>5} 键 | 中文 {sh_t:>5} ({pct(sh_t, len(sh_en))}) | 回退英文 {sh_f}")
    print(f"  动态 dynamic  : 共 {len(dy_en):>5} 键 | 中文 {dy_t:>5} ({pct(dy_t, len(dy_en))}) | 回退英文 {dy_f}")
    print("\n[OK] 已写出：")
    for f in ("frontend-zh-CN.json", "desktop-zh-CN.json", "dynamic-zh-CN.json"):
        print(f"     resources/{f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
