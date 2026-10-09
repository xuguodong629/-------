# -*- coding: utf-8 -*-
"""
_check_format.py —— 只读检查：对比知识库 md 与模板目录格式，产出差异报告。

不改动任何文件。输出：
  1) 每个目录使用的模板及其格式风格（编号型 / emoji 型）
  2) 每个文件的 frontmatter 字段差异、正文小节（## 级）差异
  3) 汇总统计
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

import core

KB = Path(r"G:\个人文件\知识库-历史\00-Inbox\历史\19民国")
TPL_DIR = KB / "Templates（模板）"
SKIP_DIR_PARTS = ("Templates", "模板", "assets", "附件", "资产")


def parse_fm_fields(text: str) -> list[str]:
    """返回 frontmatter 顶层字段名列表（有则解析，无则空）。"""
    fields, _ = core.split_frontmatter(text)
    if fields is None:
        return []
    return list(fields.keys())


def parse_h2_sections(text: str) -> list[str]:
    """返回正文所有 ## 级小节标题（原文，含序号）。"""
    _, body = core.split_frontmatter(text)
    if body is None:
        body = text
    out = []
    for line in body.splitlines():
        s = line.strip()
        if s.startswith("## ") and not s.startswith("### "):
            out.append(s[3:].strip())
    return out


def template_style(tpl_text: str) -> str:
    """判断模板格式风格。"""
    if any(ch in tpl_text for ch in ("🪪", "📌", "📜", "🏛️", "⚔️", "🔗", "📚", "📝", "📅", "👤")):
        return "emoji型"
    return "编号型"


def main() -> None:
    if not TPL_DIR.is_dir():
        print("模板目录不存在：", TPL_DIR)
        return

    # 1. 解析所有模板
    templates: dict[str, tuple[list[str], list[str], str]] = {}
    for tp in sorted(TPL_DIR.glob("*.md")):
        text = tp.read_text(encoding="utf-8")
        fm = parse_fm_fields(text)
        h2 = parse_h2_sections(text)
        templates[tp.stem] = (fm, h2, template_style(text))

    print("=" * 70)
    print("一、模板清单（字段数 / 小节数 / 风格）")
    print("=" * 70)
    for name, (fm, h2, style) in templates.items():
        print(f"  {name:<14} frontmatter {len(fm):>2} 字段 | 正文 {len(h2):>2} 小节 | {style}")

    # 2. 目录 → 模板 映射（emoji 型目录同名优先）
    cfg = core.load_config()
    routes = cfg.get("routes", {})
    dir2tpl: dict[str, str] = {}
    for tp_dir in sorted(KB.iterdir()):
        if not tp_dir.is_dir():
            continue
        dname = tp_dir.name
        # emoji 型目录同名模板优先（去数字前缀/⭐/（中文））
        norm = re.sub(r"^\d+\s*", "", dname).replace(" ⭐", "").replace("（中文）", "").strip()
        if norm in templates and templates[norm][2] == "emoji型":
            dir2tpl[dname] = norm
            continue
        # 类型路由映射（编号型）
        ttype = next((t for t, d in routes.items() if core.normalize_dir_name(d) == core.normalize_dir_name(dname)), None)
        if ttype:
            tpl = cfg.get("template_routes", {}).get(ttype)
            if tpl and tpl.removesuffix(".md") in templates:
                dir2tpl[dname] = tpl.removesuffix(".md")
                continue
        dir2tpl[dname] = "通用"

    print()
    print("=" * 70)
    print("二、目录 → 模板 映射")
    print("=" * 70)
    for d, t in dir2tpl.items():
        style = templates.get(t, ("", "", "?"))[2]
        print(f"  {d}  ->  {t}.md  ({style})")

    # 3. 扫描所有笔记，对比格式
    print()
    print("=" * 70)
    print("三、文件格式差异报告")
    print("=" * 70)

    stats = {"编号型": 0, "emoji型": 0, "匹配": 0, "fm缺失": 0, "fm多余": 0, "节缺失": 0, "节多余": 0}
    detail = []

    for tp_dir in sorted(KB.iterdir()):
        if not tp_dir.is_dir():
            continue
        if any(k.lower() in tp_dir.name.lower() for k in SKIP_DIR_PARTS):
            continue
        dname = tp_dir.name
        tpl_name = dir2tpl.get(dname, "通用")
        tpl_fm, tpl_h2, style = templates.get(tpl_name, ([], [], "编号型"))
        tpl_fm_norm = {core.header_norm(f) for f in tpl_fm}
        tpl_h2_norm = {core.header_norm(h) for h in tpl_h2}

        for md in sorted(tp_dir.glob("*.md")):
            if md.stem == "索引":
                continue
            text = md.read_text(encoding="utf-8")
            if not text.strip():
                detail.append((dname, md.stem, "空文件", "", "", "", ""))
                continue
            fm = parse_fm_fields(text)
            h2 = parse_h2_sections(text)
            fm_norm = {core.header_norm(f) for f in fm}
            h2_norm = {core.header_norm(h) for h in h2}

            fm_miss = sorted(tpl_fm_norm - fm_norm)
            fm_extra = sorted(fm_norm - tpl_fm_norm)
            h2_miss = sorted(tpl_h2_norm - h2_norm)
            h2_extra = sorted(h2_norm - tpl_h2_norm)

            # 判断该文件实际风格
            actual_style = "编号型"
            if any(h.startswith(("🪪", "📌", "📜", "🏛️", "⚔️", "🔗", "📚", "📝", "📅", "👤")) for h in h2):
                actual_style = "emoji型"

            stats[actual_style] += 1
            if not fm_miss and not h2_miss:
                stats["匹配"] += 1
            else:
                stats["fm缺失"] += len(fm_miss)
                stats["节缺失"] += len(h2_miss)
            stats["fm多余"] += len(fm_extra)
            stats["节多余"] += len(h2_extra)

            if fm_miss or h2_miss or fm_extra or h2_extra:
                detail.append((
                    dname, md.stem, actual_style,
                    "、".join(fm_miss) or "无",
                    "、".join(h2_miss) or "无",
                    "、".join(fm_extra) or "无",
                    "、".join(h2_extra) or "无",
                ))

    print(f"文件风格分布：编号型 {stats['编号型']} | emoji型 {stats['emoji型']}")
    print(f"完全匹配模板：{stats['匹配']} 个文件")
    print(f"缺失 frontmatter 字段：{stats['fm缺失']} 处")
    print(f"缺失正文小节：{stats['节缺失']} 处")
    print(f"多余 frontmatter 字段：{stats['fm多余']} 处")
    print(f"多余正文小节：{stats['节多余']} 处")
    print()

    print(f"差异明细（共 {len(detail)} 个文件）")
    print("-" * 70)
    for dname, stem, style, fm_m, h2_m, fm_e, h2_e in detail:
        print(f"[{dname}] {stem}  ({style})")
        if fm_m != "无":
            print(f"    缺字段: {fm_m}")
        if h2_m != "无":
            print(f"    缺小节: {h2_m}")
        if fm_e != "无":
            print(f"    多字段: {fm_e}")
        if h2_e != "无":
            print(f"    多小节: {h2_e}")


if __name__ == "__main__":
    main()