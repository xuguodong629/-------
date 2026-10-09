# -*- coding: utf-8 -*-
"""错位笔记体检报告（**只读**）：拿各类型目录里已有的笔记名当标准答案跑判定，找出目录与判定不符的笔记。

产出：`_报告\\错位笔记体检.md`
用法：`py _report_misplaced.py`
不搬移、不删除、不写配置 ✓ —— 搬移请用 `py _fix_skeleton_dirs.py --misplaced [--apply]`。
"""
import sys
from collections import Counter
from pathlib import Path

import core

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

KBS = [
    r"G:\个人文件\知识库-历史\00-Inbox\历史\06第一帝国时代\06-02两汉",
    r"G:\个人文件\知识库-历史\00-Inbox\历史\06第一帝国时代\06-03两晋",
    r"G:\个人文件\知识库-历史\00-Inbox\历史\06第一帝国时代\06-04十六国南北朝",
    r"G:\个人文件\知识库-历史\00-Inbox\历史\19民国",
]

# 两汉库"疑似两晋内容"的关键词（史实线索，仅用于报告提示，不参与判定 ✓）
JIN_HINTS = ("司马", "东晋", "西晋", "两晋", "衣冠南渡", "桓玄", "八王", "淝水", "王导", "谢安", "刘裕",
             "慕容", "苻", "十六国", "北魏", "前秦", "后赵", "前燕")


def cfg_for(kb: Path) -> dict:
    cfg = dict(core.load_config())
    cfg["knowledge_base"] = str(kb)
    prof = core.get_kb_profile(cfg, kb)
    for k in ("routes", "footer_types", "type_keywords"):
        if prof.get(k) is not None:
            cfg[k] = prof[k]
    return cfg


def main():
    out = core.app_dir() / "_报告" / "错位笔记体检.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# 错位笔记体检（只读）", "",
             "> 原理：**库里每个类型目录下已有的笔记名就是标准答案** —— 拿它们跑判定器，就能量出准确率、"
             "并找出“目录与判定不符”的笔记。", "",
             "> ⚠ 本报告**只报告，不搬移、不删除**。要搬移：`py _fix_skeleton_dirs.py --misplaced`（默认预览）"
             "，确认后加 `--apply`。", "",
             "| 知识库 | 扫描 | 判对 | 准确率 | 高置信错位 | 判不出（多类型库不猜/名字生僻） |",
             "| --- | --- | --- | --- | --- | --- |"]
    details = []
    summary = []
    for kbp in KBS:
        kb = Path(kbp)
        if not kb.is_dir():
            continue
        cfg = cfg_for(kb)
        rep = core.misplaced_notes(cfg, kb=kb)
        high, blank = rep["high"], rep["blank"]
        lines.append(f"| {kb.name} | {rep['scanned']} | {rep['correct']} | "
                     f"{rep['accuracy'] * 100:.1f}% | {len(high)} | {len(blank)} |")
        summary.append((kb, cfg, rep))
        details.append((kb, cfg, rep))

    for kb, cfg, rep in details:
        high = rep["high"]
        lines += ["", f"## {kb.name}", "",
                  f"- 扫描 **{rep['scanned']}** 篇｜判对 **{rep['correct']}** 篇"
                  f"（准确率 **{rep['accuracy'] * 100:.1f}%**）｜高置信错位 **{len(high)}**｜"
                  f"判不出 **{len(rep['blank'])}**"]
        # 目录"混放"判断：某目录里多数笔记的判定类型与目录类型不同 → 属库侧组织习惯，不是单篇错位
        by_dir = Counter()
        for w in high:
            by_dir[w["expected"]] += 1
        mixed_dirs = {d for d, n in by_dir.items() if n >= 3}
        if mixed_dirs:
            lines += ["",
                      f"- ⚠ **库侧混放**（这些目录里整批放着别的类型，属你的组织习惯，判定器不算错 ✗）："
                      + "、".join(f"{d}（{n} 篇）" for d, n in by_dir.most_common() if d in mixed_dirs)]
        if high:
            lines += ["", "| 笔记 | 现在目录 | 判定类型 | 判定分 | 建议去处 | 性质 |",
                      "| --- | --- | --- | --- | --- | --- |"]
            routes = dict(cfg.get("routes") or {})
            for w in high[:60]:
                tgt = str(routes.get(w["guessed"]) or "（该库无此类型）")
                kind = "库侧混放" if w["expected"] in mixed_dirs else "**单篇错位（建议搬）**"
                lines.append(f"| `{w['file'] or w['name']}` | {w['expected']} | {w['guessed']} | "
                             f"{w['score']} | {tgt} | {kind} |")
            if len(high) > 60:
                lines.append(f"| …其余 {len(high) - 60} 条略 | | | | | |")
        else:
            lines.append("- ✓ 没有高置信度错位")
        if rep["blank"]:
            lines += ["", f"<details><summary>判不出的 {len(rep['blank'])} 篇（折叠）</summary>", ""]
            for w in rep["blank"][:40]:
                lines.append(f"- `{w['file'] or w['name']}`（现在 {w['expected']}）")
            lines += ["", "</details>"]

    # 两汉库专节：当前知识库指向它，但内容疑似两晋 → 逐篇列出判定结果
    gh = Path(KBS[0])
    if gh.is_dir():
        cfg = cfg_for(gh)
        lines += ["", "## 专项：两汉库里疑似“两晋内容”的笔记", "",
                  "> 原因：①页“当前知识库”长时间停在 `06-02两汉`，而 ⑥⑦⑧ 页写入时**只会写进当前库** ✗。", "",
                  "| 笔记 | 所在目录 | 名字判定 | 是否含两晋线索 |", "| --- | --- | --- | --- |"]
        n_bad = 0
        for p in sorted(gh.rglob("*.md")):
            if core._is_skipped_path(p) or core.is_non_entry_title(p.stem):
                continue
            try:
                rel = str(p.parent.relative_to(gh))
            except Exception:
                rel = p.parent.name
            t = core.suggest_type_for_kb(cfg, p.stem) or "（判不出）"
            hint = "**是**" if any(h in p.stem for h in JIN_HINTS) else ""
            if hint:
                n_bad += 1
            lines.append(f"| `{p.name}` | {rel} | {t} | {hint} |")
        lines += ["", f"- 含“两晋线索”的笔记：**{n_bad}** 篇（按文件名判断）",
                  "- 说明：这些笔记**不是判定器写错的**，而是当时“当前知识库”就是两汉 → 写对了“当前库”，"
                  "但当前库**不该**是两汉 ✗。", "",
                  "### 那两份 `衣冠南渡.md` 的比较（未删除，等你定）", ""]
        jj = Path(KBS[1])
        for base, tag in ((gh, "两汉（错位副本）"), (jj, "两晋（正确库）")):
            for q in base.rglob("衣冠南渡.md"):
                tt = q.read_text(encoding="utf-8")
                f, bd = core.split_frontmatter(tt)
                h1 = [l for l in (bd or "").splitlines() if l.startswith("# ")][:1]
                secs = [l for l in (bd or "").splitlines() if l.startswith("## ")]
                lines.append(f"- **{tag}**：`{q.relative_to(base)}`｜{len(tt)} 字符｜"
                             f"`type={(f or {}).get('type')}`｜H1 `{h1[0][:40] if h1 else '（无）'}`｜"
                             f"{len(secs)} 个小节｜TODO {tt.count('TODO')} 处")
        p_zhanyi = gh / "03战争" / "战役.md"
        if p_zhanyi.is_file():
            lines += ["", "### 垃圾骨架 `03战争\\战役.md`（未删除，等你定）",
                      "",
                      "- 现象：文件名**就是类型名**（“战役”），frontmatter `type: 战争`，正文全是空字段 + "
                      "一个指向自己的链接 `[[战役]]` ✗",
                      "- 成因：⑧ 批量建条时把类型名当成了词条名（现在 `is_non_entry_title()` 已拦住这类 ✗→✓）",
                      "- 建议：删除（内容为空骨架；本轮**未删**，留给你确认）"]

    lines += ["", "## 换到别的朝代时怎么自查（两行）", "",
              "1. 切到新库 → 跑 `py _check_format.py --audit-types`（或 GUI ②页「🩺 类型判定体检」）："
              "**准确率 + 判错清单**一目了然；",
              "2. 判错多就把建议关键词一键写入该库档案（预览后确认 ✓）；**多时段库**（如十六国）"
              "判定器**故意不猜**时段 → 用 `类型:名称` 写。", ""]

    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"报告已写出：{out.relative_to(core.app_dir())}（{out.stat().st_size} 字节）")
    for kb, cfg, rep in summary:
        print(f"   {kb.name}：扫描 {rep['scanned']}｜准确率 {rep['accuracy'] * 100:.1f}%"
              f"｜高置信错位 {len(rep['high'])}｜判不出 {len(rep['blank'])}")


if __name__ == "__main__":
    main()
