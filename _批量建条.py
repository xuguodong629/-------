# -*- coding: utf-8 -*-
"""
批量建词条骨架：给一串关键词，自动判类型 → 套对应模板 → 存到类型对应目录（每篇只有 TODO 占位）。

用法：
    py _批量建条.py "蒋桂战争" "宁汉合流"                # 预览（不动文件）
    py _批量建条.py "蒋桂战争" "宁汉合流" --apply          # 真的建
    py _批量建条.py --file 清单.txt --apply               # 从文本文件读（每行一个）
    py _批量建条.py --from-terms 30 --apply               # 取《链接词表》里"待建词条"的前 30 条
    py _批量建条.py --type 事件 --file 清单.txt --apply    # 统一指定类型
    py _批量建条.py --dir "12 事件数据库 ⭐" --file 清单.txt  # 统一指定目录
    py _批量建条.py --overwrite --file 清单.txt --apply    # 已存在的只补空缺（不覆盖已有内容）

清单写法（每行一个，可混用）：
    蒋桂战争                # 自动判类型
    战役:昆仑关之战          # 指定类型（类型名同②页的类型映射，如 人物/事件/战役/派系/军队/条约/制度/地区/史料）
    人物:松井石根
    # 井号开头是注释
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
    overwrite = "--overwrite" in argv
    argv = [a for a in argv if a != "--overwrite"]

    type_, target_dir, file_path, from_terms, limit = "", "", "", 0, 0
    for flag, key in (("--type", "type"), ("--dir", "dir"), ("--file", "file"),
                      ("--from-terms", "terms"), ("--limit", "limit")):
        if flag in argv:
            i = argv.index(flag)
            if i + 1 < len(argv):
                val = argv[i + 1]
                if key == "type":
                    type_ = val
                elif key == "dir":
                    target_dir = val
                elif key == "file":
                    file_path = val
                else:
                    try:
                        n = int(val)
                    except ValueError:
                        n = 0
                    if key == "terms":
                        from_terms = n
                    else:
                        limit = n
                del argv[i:i + 2]

    cfg = core.load_config()
    kb = core.resolve_kb(cfg)
    print(f"知识库：{kb}")
    if kb is None:
        print("✗ 还没设置知识库目录：请先在界面①页选择，或在 config.json 里配好 knowledge_base")
        return 1

    if from_terms:                                     # 取词表里的"待建词条"
        data = core.load_term_dictionary()
        pending = [str(x) for x in (data.get("unresolved") or [])]
        good = [x for x in pending if core.looks_like_entity(x)]      # 只留像专名的（滤掉整句描述）
        if not good:
            print("✗ 词表里没有可用的待建词条（可先 py _补齐双链.py --collect-missing）")
            return 1
        good.sort(key=lambda x: (-len(x), x))
        text = "\n".join(good[:from_terms])
        print(f"从词表取待建词条 {min(from_terms, len(good))} 条"
              f"（共 {len(pending)} 条，其中像专名的 {len(good)} 条；已滤掉整句描述）")
    elif file_path:
        p = Path(file_path)
        if not p.is_file():
            print(f"✗ 找不到清单文件：{file_path}")
            return 1
        text = p.read_text(encoding="utf-8")
        print(f"从文件读取清单：{file_path}")
    else:
        text = "\n".join(argv)
    if not str(text).strip():
        print("✗ 没有关键词。示例：py _批量建条.py \"蒋桂战争\" \"宁汉合流\" --apply")
        return 1

    items = core.parse_keyword_lines(text, default_type=type_, default_dir=target_dir)
    if limit:
        items = items[:limit]
    print(f"模式：{'写入' if apply else '预览（不动文件）'}｜共 {len(items)} 个关键词"
          f"｜默认类型：{type_ or '自动判断'}｜默认目录：{target_dir or '按类型自动'}"
          f"｜已存在：{'补空缺' if overwrite else '跳过'}\n")

    r = core.create_skeleton_notes(cfg, text, type_=type_, target_dir=target_dir,
                                   dry_run=not apply, overwrite=overwrite, limit=limit,
                                   on_progress=lambda i, n, line: print(f"· [{i}/{n}] {line}"))
    print(f"\n{'已建' if apply else '将建'}：{len(r['created'])} 篇"
          f"｜跳过（已存在）：{len(r['skipped'])} 篇｜失败：{len(r['failed'])} 篇")
    if r["created"]:
        print("" + "、".join(r["created"][:30]) + ("…" if len(r["created"]) > 30 else ""))
    if r["failed"]:
        print("失败：" + "、".join(r["failed"][:20]))
    if not apply and r["created"]:
        print("确认无误后加 --apply 写盘（新建不会覆盖任何已有内容）。")
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
