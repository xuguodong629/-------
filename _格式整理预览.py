# -*- coding: utf-8 -*-
"""
_格式整理预览.py —— 只读预览：知识库里哪些笔记按格式规范整理后会变、内容会不会丢。

用法：
    py _格式整理预览.py                # 全部笔记（最多 --limit 篇）
    py _格式整理预览.py --limit 80     # 只看前 80 篇
    py _格式整理预览.py "派系"          # 只看向包含「派系」的词条

说明：**只读，不写任何文件**。要真的整理某篇，用界面 ⑦「补充更新」页选那篇点
「📐 按格式规范整理整篇」；整理前程序会自动把旧版备份到 `_备份/笔记/`。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

import core


def content_lines(text: str) -> int:
    """粗略统计"实质内容行"（排除 TODO / frontmatter / 页脚）。"""
    return sum(1 for x in (text or "").splitlines()
               if x.strip() and "TODO" not in x and not x.startswith(("---", "**关联**")))


def main() -> int:
    argv = list(sys.argv[1:])
    limit = 200
    if "--limit" in argv:
        i = argv.index("--limit")
        if i + 1 < len(argv):
            try:
                limit = int(argv[i + 1])
            except ValueError:
                pass
            del argv[i:i + 2]
    keyword = argv[0] if argv else ""
    cfg = core.load_config()
    notes = core.list_notes(cfg, keyword)
    print(f"知识库：{cfg.get('knowledge_base')}")
    print(f"待检查 {min(len(notes), limit)} 篇（共 {len(notes)} 篇，关键词「{keyword or '（全部）'}」）\n")
    changed, same, lost = [], 0, []
    for n in notes[:limit]:
        p = Path(n["path"])
        try:
            before = p.read_text(encoding="utf-8")
        except Exception:
            continue
        r = core.update_note_file(cfg, p, dry_run=True)
        after = r.get("text") or ""
        if content_lines(after) < content_lines(before):
            lost.append((f"{n['dir']}/{n['title']}", content_lines(before), content_lines(after)))
        if after.strip() == before.strip():
            same += 1
        else:
            changed.append((f"{n['dir']}/{n['title']}", r.get("report") or []))
    for name, rep in changed[:30]:
        print(f"· {name}.md → {'；'.join(rep[:3]) or '（格式归一：空行/页脚/标题层级）'}")
    if len(changed) > 30:
        print(f"（其余 {len(changed) - 30} 篇略）")
    print(f"\n会调整 {len(changed)} 篇、保持不变 {same} 篇")
    if lost:
        print("⚠ 以下笔记整理后内容行会变少（请先反馈，不要直接整理）：")
        for name, a, b in lost[:20]:
            print(f"    {name}：{a} → {b}")
        return 1
    print("✓ 没有任何笔记会因为整理而丢内容")
    return 0


if __name__ == "__main__":
    sys.exit(main())
