# -*- coding: utf-8 -*-
"""
_fix_lifeline.py —— 把人物笔记的「📜 生平简史」从大段散文改写成时间线阶段条目（格式规范 §2.2）。

改写规则（**原文一个字不删**，只重排 + 加年份标签）：
  * 原句按「。；！？」切分，按文中**明确出现的年份**分组；
  * 阶段标签 = `起始年-结束年`：结束年取下一阶段的起始年前一年；
    最后一个阶段用 frontmatter 的逝世年；第一阶段缺年份时用出生年；
  * 一整段里都找不到年份的阶段 → 标 `年份待补`（**绝不编造年份**）；
  * 文中年份少于 2 个（信息不足，切不出阶段）→ 该笔记跳过，留给人工；
  * 正文 `[[双链]]`、标点、措辞全部原样保留。

安全措施：
  * 默认 **dry-run**，只打印样例与统计；`--apply` 才写；
  * `--show 文件` 看单篇前后对照；
  * `--apply` 时逐文件备份到 `_备份/笔记/`（统一备份目录，同名只留最新一份）。

用法：
    py _fix_lifeline.py                      # 预览（默认知识库 02 人物图谱）
    py _fix_lifeline.py --show 丁汝昌.md
    py _fix_lifeline.py --apply              # 逐文件备份后改写
    py _fix_lifeline.py --dir "06 共产党形成史" --apply
"""
from __future__ import annotations

import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import core

SECTION_KEY = "生平简史"
YEAR_RE = re.compile(r"(?<!\d)(1[89]\d{2})(?!\d)")
SENT_SPLIT_RE = re.compile(r"(?<=[。；！？])")
SKIP_DIR_PARTS = ("templates", "模板", "assets", "attachments", "附件", "资产", "图片")


def split_sentences(text: str) -> list:
    return [s.strip() for s in SENT_SPLIT_RE.split(text) if s.strip()]


def years_in(text: str) -> list:
    return [int(y) for y in YEAR_RE.findall(text)]


def convert_lifeline(sentences: list, born: str, died: str) -> tuple:
    """原句 → 时间线阶段条目。返回 (条目列表, 阶段数)。"""
    stages: list = []            # [[起始年 or None, [句子…]], …]
    for sent in sentences:
        ys = years_in(sent)
        start = ys[0] if ys else None
        cur = stages[-1][0] if stages else None
        if start is not None and (cur is None or start > cur):
            stages.append([start, [sent]])
        elif stages:
            stages[-1][1].append(sent)
        else:
            stages.append([start, [sent]])
    if stages and stages[0][0] is None and years_in(born or ""):
        stages[0][0] = years_in(born)[0]

    died_year = years_in(died or "")
    out = []
    for i, (year, sents) in enumerate(stages):
        nxt = stages[i + 1][0] if i + 1 < len(stages) else None
        if year is None:
            label = "年份待补"
        elif nxt is not None:
            end = nxt - 1
            label = str(year) if end <= year else f"{year}-{end}"
        elif died_year:
            label = str(year) if died_year[0] <= year else f"{year}-{died_year[0]}"
        else:
            label = f"{year} 起"
        out.append(f"- **{label}**：" + "".join(sents))
    return out, len(stages)


def plan_for(path: Path) -> tuple:
    """返回 (新小节行 或 None, 状态说明)。"""
    text = path.read_text(encoding="utf-8")
    fields, body = core.split_frontmatter(text)
    fields = fields or {}
    sections = core.parse_sections(body or "")
    key = next((k for k in sections if SECTION_KEY in k), None)
    if key is None:
        return None, "没有生平简史小节"
    lines = sections[key][1]
    real = [ln.strip() for ln in lines if ln.strip()]
    if not real:
        return None, "生平简史是空/TODO（等 AI 填）"
    if all(ln.startswith(("-", "*")) for ln in real):
        return None, "已经是条目形式"
    prose = " ".join(ln for ln in real if not ln.startswith("<!--"))
    sentences = split_sentences(prose)
    if len({y for y in years_in(prose)}) < 2:
        return None, f"文中只有 {len(set(years_in(prose)))} 个年份，切不出阶段（跳过）"
    items, n = convert_lifeline(sentences, str(fields.get("born", "")), str(fields.get("died", "")))
    if n < 2:
        return None, "只切出 1 个阶段（跳过）"
    return items, f"散文 → {n} 个阶段"


def rewrite_note(path: Path, items: list) -> str:
    """只替换「生平简史」小节的正文；frontmatter 与其它小节**逐字保留**。"""
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    all_lines = text.split("\n")
    head: list = []
    start = 0
    if all_lines and all_lines[0].strip() == "---":
        for i in range(1, len(all_lines)):
            if all_lines[i].strip() == "---":
                head = all_lines[:i + 1]
                start = i + 1
                break
    lines = all_lines[start:]
    out, i, done = [], 0, False
    while i < len(lines):
        ln = lines[i]
        m = re.match(r"^(#{2,3})\s+(.*)$", ln)
        if m and SECTION_KEY in m.group(2):
            out.append(ln)
            i += 1
            while i < len(lines) and not re.match(r"^(#{2,3})\s+", lines[i]):
                i += 1
            out.append("")
            out.extend(items)
            out.append("")
            done = True
            continue
        out.append(ln)
        i += 1
    if not done:
        return text
    while out and not out[-1].strip():
        out.pop()
    body = "\n".join(out).strip("\n") + "\n"
    if head:
        return "\n".join(head) + "\n\n" + body
    return body


def iter_notes(root: Path, only_dir: str = ""):
    dirs = [root / only_dir] if only_dir else sorted(p for p in root.iterdir() if p.is_dir())
    for d in dirs:
        if not d.is_dir() or any(k in d.name.lower() for k in SKIP_DIR_PARTS):
            continue
        for p in sorted(d.glob("*.md")):
            if p.stem != "索引":
                yield p


def main() -> int:
    args = list(sys.argv[1:])
    apply_ = "--apply" in args
    args = [a for a in args if a != "--apply"]
    show = ""
    if "--show" in args:
        i = args.index("--show")
        if i + 1 < len(args):
            show = args[i + 1]
            del args[i:i + 2]
    only_dir = ""
    if "--dir" in args:
        i = args.index("--dir")
        if i + 1 < len(args):
            only_dir = args[i + 1]
            del args[i:i + 2]
    root = Path(args[0]) if args else Path(core.DEFAULT_KB_HINT)
    if not root.is_dir():
        print("知识库路径不存在：", root)
        return 1
    if not only_dir:
        only_dir = "02 人物图谱"

    if show:
        p = next((q for q in iter_notes(root, only_dir) if q.name == show or q.stem == show), None)
        if p is None:
            print("没找到：", show)
            return 1
        items, why = plan_for(p)
        print(f"=== {p.parent.name}/{p.name}  {why} ===")
        _fields, body = core.split_frontmatter(p.read_text(encoding="utf-8"))
        sec = core.parse_sections(body or "")
        key = next(k for k in sec if SECTION_KEY in k)
        print("--- 改前 ---")
        print("\n".join(ln for ln in sec[key][1] if ln.strip())[:1400])
        print("--- 改后（文件片段） ---")
        if not items:
            print("（不改）")
            return 0
        new_lines = rewrite_note(p, items).splitlines()
        k = next((j for j, ln in enumerate(new_lines)
                  if ln.startswith("#") and SECTION_KEY in ln), None)
        print("\n".join(new_lines[k:k + len(items) + 3]) if k is not None else "\n".join(items))
        return 0

    plan, skipped = [], {}
    for p in iter_notes(root, only_dir):
        items, why = plan_for(p)
        if items:
            plan.append((p, items))
        else:
            skipped[why] = skipped.get(why, 0) + 1

    print("=" * 72)
    print(f"生平简史时间线化（{'写盘' if apply_ else '预览'}）：{root} / {only_dir}")
    print("=" * 72)
    print(f"可改写：{len(plan)} 篇；跳过：{sum(skipped.values())} 篇")
    for why, n in sorted(skipped.items(), key=lambda kv: -kv[1]):
        print(f"    跳过原因 {why}：{n} 篇")
    print("-" * 72)
    for p, items in plan[:3]:
        print(f"[样例] {p.name}")
        for ln in items:
            print("   " + ln[:150])
        print()
    if not apply_:
        print(f"这是预览（共 {len(plan)} 篇可改）；确认后加 --apply 执行（逐文件备份）。")
        print("想看某一篇的完整前后对照：py _fix_lifeline.py --show 丁汝昌.md")
        return 0

    for p, items in plan:
        core.backup_note(p, root)                    # 统一备份：_备份/笔记/<相对路径>（只留最新）
        p.write_text(rewrite_note(p, items), encoding="utf-8")
    print(f"已改写 {len(plan)} 篇的生平简史（原文件备份到 {core.BACKUP_DIR_NAME}/笔记/，同名只留最新一份）。")
    print("回滚：把 _备份/笔记/ 里的文件按同路径拷回知识库即可。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
