# -*- coding: utf-8 -*-
"""十六国南北朝 库：修"带路径红链" + 清 frontmatter 里的 [[ ]] + 出争议清单 + 出结构报告。

用法：
    py _fix_sixteen.py            # 只预览（不动任何文件）
    py _fix_sixteen.py --apply    # 备份 → 写入 → 复检
原则：只改链接目标与 frontmatter 内的链接写法，绝不动其它文字、绝不猜、绝不编造。
"""
from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

import core
import _check_spec

KB = Path(r"G:\个人文件\知识库-历史\00-Inbox\历史\06第一帝国时代\06-04十六国南北朝")
BACKUP = core.app_dir() / "_备份" / "十六国南北朝_修复前"
REPORT_DIR = core.app_dir() / "_报告"
LINK_RE = re.compile(r"(?<!!)\[\[([^\]|]+?)(\|[^\]]+)?\]\]")


def count_path_links(text: str) -> int:
    return sum(1 for m in LINK_RE.finditer(text)
               if "/" in m.group(1) or "\\" in m.group(1))


def count_fm_links(text: str) -> int:
    if not text.startswith("---"):
        return 0
    end = text.find("\n---", 3)
    if end == -1:
        return 0
    return len(re.findall(r"\[\[[^\]]+\]\]", text[: end + 4]))


def audit(notes: list, stems: set) -> dict:
    """只读体检：硬问题篇数 / 带路径链接 / frontmatter 链接 / 红链（带路径 / 纯名字）。"""
    hard, path_links, fm_links, red_path, red_plain = 0, 0, 0, 0, 0
    for p in notes:
        t = p.read_text(encoding="utf-8")
        if _check_spec.check_text(t):
            hard += 1
        path_links += count_path_links(t)
        fm_links += count_fm_links(t)
        for m in LINK_RE.finditer(t):
            tgt = m.group(1).strip()
            if tgt in stems:
                continue
            if "/" in tgt or "\\" in tgt:
                red_path += 1
            else:
                red_plain += 1
    return {"hard": hard, "path_links": path_links, "fm_links": fm_links,
            "red_path": red_path, "red_plain": red_plain, "total": len(notes)}


def main() -> int:
    apply = "--apply" in sys.argv
    if not KB.is_dir():
        print(f"✗ 目标库不存在：{KB}")
        return 1
    notes = [p for p in sorted(KB.rglob("*.md")) if not core._is_skipped_path(p)]
    stems = {p.stem for p in KB.rglob("*.md")}
    print(f"库：{KB.name}｜笔记 {len(notes)} 篇｜库内笔记名 {len(stems)} 个")
    print(f"模式：{'写入（先备份）' if apply else '预览（不动文件）'}")
    b = audit(notes, stems)
    print(f"改前：规范不通过 {b['hard']} 篇｜带路径链接 {b['path_links']} 处"
          f"｜frontmatter 内 [[ ]] {b['fm_links']} 处"
          f"｜红链 带路径 {b['red_path']} + 纯名字 {b['red_plain']}")

    cnt = {"path": 0, "still_red": 0, "fm": 0}
    changed, fm_bad = [], []
    for p in notes:
        text = orig = p.read_text(encoding="utf-8")

        def body_repl(m):
            target, disp = m.group(1).strip(), m.group(2) or ""
            if "/" not in target and "\\" not in target:
                return m.group(0)
            last = re.split(r"[\\/]", target)[-1].strip()
            if not last:
                return m.group(0)
            cnt["path"] += 1
            if last not in stems:
                cnt["still_red"] += 1
            return f"[[{last}{disp}]]"
        text = LINK_RE.sub(body_repl, text)

        if text.startswith("---"):
            end = text.find("\n---", 3)
            if end != -1:
                head, rest = text[: end + 4], text[end + 4:]

                def fm_repl(m):
                    cnt["fm"] += 1
                    target = m.group(1).strip()
                    disp = (m.group(2) or "")[1:].strip()
                    return disp or target
                text = re.sub(r"\[\[([^\]|]+?)(\|[^\]]+)?\]\]", fm_repl, head) + rest
                if core.split_frontmatter(text)[0] is None:
                    fm_bad.append(p.name)

        if text != orig:
            changed.append(p)
            if apply:
                dest = BACKUP / p.relative_to(KB)
                dest.parent.mkdir(parents=True, exist_ok=True)
                if not dest.exists():
                    shutil.copy2(p, dest)
                core.write_text_keep_eol(p, text)

    print(f"{'已改' if apply else '将改'}：{len(changed)} 篇｜去路径链接 {cnt['path']} 处"
          f"（去路径后仍红 {cnt['still_red']} 处）｜frontmatter 去链接 {cnt['fm']} 处")
    if fm_bad:
        print(f"  ✗ frontmatter 解析异常：{fm_bad}")
    print("  示例：", [str(x.relative_to(KB)) for x in changed[:5]])
    if apply:
        print(f"  备份：{BACKUP}")
        a = audit(notes, stems)
        print(f"改后：规范不通过 {a['hard']} 篇（改前 {b['hard']}）"
              f"｜带路径链接 {a['path_links']}（改前 {b['path_links']}）"
              f"｜frontmatter 内 [[ ]] {a['fm_links']}（改前 {b['fm_links']}）"
              f"｜红链 带路径 {a['red_path']}（改前 {b['red_path']}）"
              f" + 纯名字 {a['red_plain']}（改前 {b['red_plain']}）")

    # ---------- 第 3 项：争议缺来源清单 ----------
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    miss = []
    for p in notes:
        for i, ln in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if core.DISPUTE_MARK in ln and "来源" not in ln:
                miss.append((p, i, ln.strip()))
    lines = ["# 十六国南北朝 · 争议说明缺来源清单", "",
             f"共 **{len(miss)}** 处（判定：该行含 `⚖️ 争议说明` 但没有 `｜来源：`）。", "",
             "| # | 文件 | 行号 | 原文 |", "| --- | --- | --- | --- |"]
    for i, (p, no, txt) in enumerate(miss, 1):
        safe = txt.replace("|", "\\|")[:160]
        lines.append(f"| {i} | {p.relative_to(KB)} | {no} | {safe} |")
    (REPORT_DIR / "十六国南北朝_争议缺来源.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\n争议缺来源 {len(miss)} 处 → _报告/十六国南北朝_争议缺来源.md")

    # ---------- 第 5 项：结构报告 + 推荐映射（只建议，不写配置） ----------
    struct: dict = {}
    for p in notes:
        key = "/".join(p.relative_to(KB).parts[:-1]) or "（库根）"
        struct[key] = struct.get(key, 0) + 1
    rows = sorted(struct.items(), key=lambda x: (-x[1], x[0]))
    lines = ["# 十六国南北朝 · 目录结构统计", "",
             f"笔记合计 **{len(notes)}** 篇，分布在 **{len(rows)}** 个子目录：", "",
             "| 子目录 | 篇数 |", "| --- | --- |"]
    lines += [f"| {k} | {v} |" for k, v in rows]
    lines += ["", "## 推荐映射（仅建议，未写入 config.json）", ""]
    for k, v in rows:
        parts = k.split("/")
        if len(parts) >= 2:
            lines.append(f"- `{parts[0]}` 若按时段分：**{parts[0]}-{parts[1]}** → `{k}`（{v} 篇）")
    lines += ["", "- 或在②页把映射直接指到子目录，例如 `人物 → 01人物/五胡十六国`。"]
    (REPORT_DIR / "十六国南北朝_结构.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("结构报告 → _报告/十六国南北朝_结构.md")
    print("  前 8 个子目录：", [f"{k}({v})" for k, v in rows[:8]])
    return 0


if __name__ == "__main__":
    sys.exit(main())
