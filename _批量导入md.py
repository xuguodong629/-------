# -*- coding: utf-8 -*-
"""
从 md 文档批量建库：一份 md → 拆成多个词条 → 自动判类型 → 套该类型的**规范模板** →
→ 存到类型对应目录；已有同名词条时**只补空缺、不覆盖正文**。

用法：
    py _批量导入md.py "书稿.md"                  # 预览：拆出哪些词条、各判成什么类型
    py _批量导入md.py "书稿.md" --list            # 只列词条清单（名称+级别+正文字数）
    py _批量导入md.py "书稿.md" --apply           # 真正建立（写前备份；目录需已存在）
    py _批量导入md.py "书稿.md" --level 2 --apply  # 指定按第 2 级标题（##）拆分
    py _批量导入md.py "书稿.md" --type 人物 --apply # 统一指定类型（覆盖自动判断）
    py _批量导入md.py "书稿.md" --dir "02 人物图谱" --apply   # 统一指定目录
    py _批量导入md.py "书稿.md" --limit 20 --apply  # 只处理前 20 个词条
    py _批量导入md.py "书稿.md" --download-images --apply     # 顺带把正文里的网络图片存进 Assets

文档要求（很宽松）：
    * 用标题分条（`# 袁世凯` / `## 袁世凯` 都可以，程序会自动挑"重复出现的最浅级别"）；
    * 每条正文可以是任意 Markdown（`## 小节`、表格、列表都行）；
    * 想指定类型：在词条开头写 `类型: 人物`（或 frontmatter `type: 人物`），也支持命令行 --type 统一指定；
    * 文档开头的 frontmatter 视为整篇元数据；代码块里的 # 不当标题。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

import core


def main() -> int:
    argv = list(sys.argv[1:])
    apply = "--apply" in argv
    argv = [a for a in argv if a != "--apply"]
    list_only = "--list" in argv
    argv = [a for a in argv if a != "--list"]
    dl = "--download-images" in argv
    argv = [a for a in argv if a != "--download-images"]

    level, limit, type_, target_dir = 0, 0, "", ""
    for flag, key in (("--level", "level"), ("--limit", "limit"),
                      ("--type", "type"), ("--dir", "dir")):
        if flag in argv:
            i = argv.index(flag)
            if i + 1 < len(argv):
                val = argv[i + 1]
                if key == "type":
                    type_ = val
                elif key == "dir":
                    target_dir = val
                else:
                    try:
                        n = int(val)
                    except ValueError:
                        n = 0
                    if key == "level":
                        level = n
                    else:
                        limit = n
                del argv[i:i + 2]

    if not argv:
        print(__doc__)
        return 1
    src = Path(argv[0])
    if not src.is_file():
        print(f"✗ 找不到文件：{src}")
        return 1
    text = src.read_text(encoding="utf-8")
    cfg = core.load_config()
    kb = core.resolve_kb(cfg)
    print(f"知识库：{kb}\n文档：{src}（{len(text)} 字符）")

    entries = core.split_markdown_entries(text, level=level)
    if not entries:
        print("✗ 这份文档里没找到可拆分的标题（至少要有两个同级标题，或用 --level 指定）")
        return 1
    print(f"按第 {entries[0]['level']} 级标题拆分：共 {len(entries)} 个词条"
          f"（{'只看清单' if list_only else ('写入' if apply else '预览')}）\n")
    if list_only:
        for i, e in enumerate(entries, 1):
            print(f"  [{i:>3}] {e['title']}   （正文 {len(e['body'])} 字｜"
                  f"自带类型：{(e['meta'] or {}).get('类型') or (e['meta'] or {}).get('type') or '—'}）")
        return 0

    r = core.import_markdown_document(cfg, text, level=level, type_override=type_,
                                      target_dir=target_dir, dry_run=not apply,
                                      download_images=dl, limit=limit,
                                      on_progress=lambda i, n, line: print(f"· [{i}/{n}] {line}"))
    if limit:
        print(f"\n（共 {r['total']} 篇，已按 --limit {limit} 截取）")
    print(f"\n{'已建' if apply else '将建'}：{len(r['created'])} 篇"
          f"｜跳过（已存在且无内容可补）：{len(r['skipped'])} 篇｜失败：{len(r['failed'])} 篇")
    if r["failed"]:
        print("失败：" + "、".join(r["failed"][:20]))
    if not apply and r["created"]:
        print("确认无误后加 --apply 写盘（缺目录会自动创建；写前备份到 _备份/笔记/）。")
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
