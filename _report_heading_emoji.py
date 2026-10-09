# -*- coding: utf-8 -*-
"""规范漏报体检：用修复后的 §1-4 emoji 判定重跑各知识库，输出 _报告/规范漏报体检.md。

只读脚本：不改任何笔记、不改配置。

背景：`_check_spec.py` 曾用 `ord(ch) >= 0x2190` 判断标题是否已带 emoji ——
汉字（>= U+4E00）全部 >= 0x2190，于是**中文开头的标题一律被当成「已带 emoji」**，
只有数字/字母开头的才会被抓到 → §1-4 长期系统性漏报。
修复后重跑，§1-4 数量**上升 = 原来被静默放过的问题被暴露**（不是新问题）。

用法：py _report_heading_emoji.py [--limit N]
"""
from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

import core
import _check_spec as cs

KBS = [
    ("06-02两汉", r"G:\个人文件\知识库-历史\00-Inbox\历史\06第一帝国时代\06-02两汉"),
    ("06-03两晋", r"G:\个人文件\知识库-历史\00-Inbox\历史\06第一帝国时代\06-03两晋"),
    ("06-04十六国南北朝", r"G:\个人文件\知识库-历史\00-Inbox\历史\06第一帝国时代\06-04十六国南北朝"),
    ("19民国", r"G:\个人文件\知识库-历史\00-Inbox\历史\19民国"),
]

HEAD = [
    "# 规范漏报体检（§1-4 emoji 判定修复后重跑）",
    "",
    "> 旧判定用 `ord(ch) >= 0x2190` -> 汉字全部命中 -> 中文开头的标题被当成「已带 emoji」-> §1-4 系统性漏报。",
    "> 修复后重跑：**§1-4 数量上升 = 原来被静默放过的问题被暴露**（不是新问题）。",
    "",
]


def scan(kb: Path, sample_limit: int = 20) -> dict:
    files = [
        x
        for x in sorted(kb.rglob("*.md"))
        if not core._is_skipped_path(x) and not x.stem.endswith("索引")
    ]
    total = bad = 0
    emoji_items: list[tuple[str, str]] = []
    dirs: Counter = Counter()
    for p in files:
        total += 1
        try:
            issues = cs.check_text(p.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            issues = [f"读取失败：{exc}"]
        if not issues:
            continue
        bad += 1
        for x in issues:
            if "emoji" in x or "§1-4" in x:
                m = re.search(r"：(.+)$", x)
                emoji_items.append((str(p.relative_to(kb)), (m.group(1) if m else x).strip()))
                dirs[str(p.parent.relative_to(kb))] += 1
    return {"total": total, "bad": bad, "items": emoji_items, "dirs": dirs}


def main() -> int:
    sample_limit = 20
    if "--limit" in sys.argv:
        try:
            sample_limit = int(sys.argv[sys.argv.index("--limit") + 1])
        except Exception:  # noqa: BLE001
            pass
    lines = list(HEAD)
    summary = []
    for name, path in KBS:
        kb = Path(path)
        if not kb.is_dir():
            lines += [f"## {name}", "", "（目录不存在，跳过）", ""]
            continue
        r = scan(kb, sample_limit)
        summary.append((name, r["total"], r["bad"], len(r["items"])))
        lines += [
            f"## {name}",
            "",
            f"- 扫描词条笔记：**{r['total']}** 篇｜有问题 **{r['bad']}** 篇"
            f"｜其中 **§1-4（标题缺 emoji）：{len(r['items'])} 处**",
            "",
        ]
        if r["items"]:
            lines += ["### §1-4 样例", "", "| 文件 | 标题 |", "| --- | --- |"]
            lines += [f"| {f} | `{t}` |" for f, t in r["items"][:sample_limit]]
            lines += ["", "### 按目录分组", "", "| 目录 | 处数 |", "| --- | --- |"]
            lines += [f"| {d} | {c} |" for d, c in r["dirs"].most_common()]
            if len(r["items"]) > sample_limit:
                lines += ["", f"（其余 {len(r['items']) - sample_limit} 条略）"]
            lines += [""]
        else:
            lines += ["（该库 §1-4 无问题）", ""]
    lines += [
        "## 建议与工作量",
        "",
        "- 本轮**只修判定 + 出报告，未批量补 emoji**（需要你点头再做）。",
        "- 修法：按各笔记**自身已有小节的 emoji 风格**补前缀（标题文字不改）；`###` 子标题同样需要前缀。",
        "- 建议顺序：先在 1 篇上试 → 渲染确认 → 再按目录分批推广；每批先备份。",
    ]
    out = core.app_dir() / "_报告" / "规范漏报体检.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"报告已写：{out}")
    print(f"{'库':<20}{'扫描':>6}{'有问题':>8}{'§1-4':>8}")
    for n, t, b, e in summary:
        print(f"{n:<20}{t:>6}{b:>8}{e:>8}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
