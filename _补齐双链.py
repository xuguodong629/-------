# -*- coding: utf-8 -*-
"""
_补齐双链.py —— 给笔记正文里出现的知识库词条自动补 `[[双链]]`（全库批量）。

用法：
    py _补齐双链.py                     # 预览：本地匹配（词条名/别名/去年前缀/事件简称）
    py _补齐双链.py --ai --limit 3       # **AI 专名模式**：识别通称、异名、库里还没有的专名（每篇一次调用）
    py _补齐双链.py --ai --no-red        # AI 模式但不写"待建链接"（报告里仍会列出该建哪些词条）
    py _补齐双链.py --limit 20          # 只试前 20 篇
    py _补齐双链.py "派系"               # 只处理目录/标题含「派系」的笔记
    py _补齐双链.py --all-occurrences   # 同一个词条每次出现都链（默认只链第一次）
    py _补齐双链.py --with-headings     # 标题行也链（默认跳过标题行）
    py _补齐双链.py --apply             # 真的写盘（每篇写前自动备份到 _备份/笔记/）
    py _补齐双链.py --one ""<类型目录>/<词条名>.md""   # 只处理一篇（给相对路径或绝对路径）

规则：
    * frontmatter、已有 `[[ ]]`、图片、行内代码、网址一律不动；
    * 代码块内不动；标题行默认跳过；
    * 长的词条名优先（「日本陆军」不会被「日本」吃掉）；不给自己加链；
    * 通用短名（中国/日本/美国/英国/苏联…）默认不链，可在 config.json 里用
      "link_skip_words": ["…"] 覆盖；
    * 每篇最多 80 个链接（可用 --max 调）。
    * **AI 模式**下：AI 只挑名字且要求逐字出现在正文里（防编造）；能对上库内词条就写成
      `[[真实词条名|正文写法]]`（保证 Obsidian 能解析），对不上的按"待建链接"处理并列出清单。

**批量替换纪律（血泪教训，README 里也写了一份）**：
    1. 凡对大范围文本做批量替换，**必须先在 1 个文件上试 → 渲染确认 → 再推广**；
    2. 规则**不得"移动字符"**（不得把字符从一处搬到另一处，例如把引号/管道符搬进别的结构）
       —— **只允许"删除"或"替换为固定串"**；
    3. 批量替换前先备份、替换后立刻用 `py _check_format.py --syntax`（Markdown 结构体检）复检。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

import core


def clean_red_links(cfg: dict, kb, apply: bool) -> int:
    """把 `[[未建词条]]` 红链转回纯文本（管道链接只留显示写法）；可解析的链接原样保留。"""
    names = {p.stem for p in kb.rglob("*.md") if not core._is_skipped_path(p)}
    touched = total = 0
    for n in core.list_notes(cfg):
        p = Path(n["path"])
        try:
            text = p.read_text(encoding="utf-8")
        except Exception:
            continue

        def repl(m):
            target = m.group(1).strip()
            disp = (m.group(2) or "").strip()
            if target in names:
                return m.group(0)                     # 能解析：保留
            return disp or target                     # 红链：转回纯文本
        new = re.sub(r"(?<!!)\[\[([^\]|]+)(?:\|([^\]]+))?\]\]", repl, text)
        if new == text:
            continue
        cnt = len(re.findall(r"(?<!!)\[\[", text)) - len(re.findall(r"(?<!!)\[\[", new))
        touched += 1
        total += cnt
        if apply:
            core.backup_note(p, kb)
            core.write_text_keep_eol(p, new)
        if touched <= 25:
            print(f"· {n['dir']}/{n['title']} → 清理 {cnt} 个红链")
    print(f"\n{'已' if apply else '将'}清理红链：{touched} 篇、共 {total} 个"
          + ("" if apply else "（加 --apply 执行，每篇写前自动备份）"))
    return 0


def main() -> int:
    argv = list(sys.argv[1:])
    clean_red = "--clean-red" in argv
    argv = [a for a in argv if a != "--clean-red"]
    use_red = "--red" in argv                          # 本地引擎是否也写"待建链接"（默认不写）
    argv = [a for a in argv if a != "--red"]
    rebuild = "--rebuild-terms" in argv
    argv = [a for a in argv if a != "--rebuild-terms"]
    collect = "--collect-missing" in argv
    argv = [a for a in argv if a != "--collect-missing"]
    apply = "--apply" in argv
    argv = [a for a in argv if a != "--apply"]
    use_ai = "--ai" in argv
    argv = [a for a in argv if a != "--ai"]
    red_links = "--no-red" not in argv
    argv = [a for a in argv if a != "--no-red"]
    first_only = "--all-occurrences" not in argv
    argv = [a for a in argv if a != "--all-occurrences"]
    skip_headings = "--with-headings" not in argv
    argv = [a for a in argv if a != "--with-headings"]
    limit, max_links, top, max_red, offset, workers = 0, 80, 0, 12, 0, 1
    for flag, target in (("--limit", "limit"), ("--max", "max"), ("--top", "top"),
                         ("--max-red", "max_red"), ("--offset", "offset"),
                         ("--workers", "workers")):
        if flag in argv:
            i = argv.index(flag)
            if i + 1 < len(argv):
                try:
                    value = int(argv[i + 1])
                except ValueError:
                    value = 0
                if target == "limit":
                    limit = value
                elif target == "max":
                    max_links = value or 80
                elif target == "top":
                    top = value
                elif target == "max_red":
                    max_red = max(0, value)
                elif target == "offset":
                    offset = max(0, value)
                else:
                    workers = max(1, min(6, value or 1))
                del argv[i:i + 2]
    one = ""
    if "--one" in argv:
        i = argv.index("--one")
        if i + 1 < len(argv):
            one = argv[i + 1]
            del argv[i:i + 2]
    keyword = argv[0] if argv else ""

    cfg = core.load_config()
    kb = core.resolve_kb(cfg)
    if clean_red:                                      # 把未建词条的红链转回纯文本
        print(f"知识库：{kb}\n模式：{'写入' if apply else '预览（不动文件）'}")
        return clean_red_links(cfg, kb, apply)
    if collect:                                        # 汇总"待建词条"（含备份里的红链）写进词表
        data = core.load_term_dictionary()
        if not data:
            data = core.build_term_dictionary(cfg, save=True)
        missing = core.collect_missing_terms(cfg, include_backups=True)
        data["unresolved"] = missing
        core.term_dict_path().write_text(
            __import__("json").dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"已汇总待建词条：{len(missing)} 条 → {core.term_dict_path()}")
        print("   出现最多的 20 条：" + "、".join(missing[:20]))
        return 0
    if rebuild:                                        # 只重建词表（零 token，供本地引擎用）
        data = core.build_term_dictionary(cfg, save=True)
        print(f"已重建链接词表：{core.term_dict_path()}")
        print(f"   写法 {len(data.get('terms') or {})} 条｜其中库内还没有的 {len(data.get('unresolved') or [])} 条")
        top = sorted((data.get("unresolved") or []), key=lambda x: -len(str(x)))[:20]
        if top:
            print("   待建词条示例：" + "、".join(top))
        return 0
    print(f"知识库：{kb}")
    mode = "写入" if apply else "预览（不动文件）"
    engine = "AI 专名（含通称/异名/待建词条）" if use_ai else "本地词条名匹配"
    print(f"模式：{mode}｜引擎：{engine}｜每个词条只链第一次：{first_only}｜"
          f"跳过标题行：{skip_headings}｜每篇上限：{max_links}｜待建链接：{red_links}\n")

    if use_ai:                                          # AI 逐篇识别专名（每篇一次调用，慢且花钱）
        if core.ai_client_from_config(cfg) is None:
            print("✗ AI 模式需要 API Key（请在界面 AI 设置里配置后再试）")
            return 1
        print("⚠ AI 模式每篇都要调用一次模型（比本地匹配慢、也更花钱），建议先加 --limit 3 试几篇。\n")

    if one:
        p = Path(one)
        if not p.is_absolute() and kb is not None:
            p = kb / one
        if use_ai:
            r = core.link_keywords_ai(cfg, p, dry_run=not apply, red_links=red_links,
                                      first_only=first_only, skip_headings=skip_headings,
                                      max_links=max_links, max_red=max_red)
        else:
            r = core.link_keywords(cfg, p, dry_run=not apply, first_only=first_only,
                                   skip_headings=skip_headings, max_links=max_links,
                                   only_resolved=not use_red)
        if not r.get("ok"):
            print("✗ " + "；".join(r.get("report") or ["失败"]))
            return 1
        print(f"· {p.name} → {r.get('action')}")
        for line in (r.get("report") or [])[:4]:
            print("   · " + str(line)[:200])
        if r.get("added"):
            print("   新增：" + "、".join(f"[[{a}]]" for a in r["added"][:16]))
        return 0

    notes = core.list_notes(cfg, keyword)
    if top:                                             # 按篇幅挑最值得补的 N 篇（跳过首页/索引）
        pool = [n for n in notes if "首页" not in n["dir"] and "索引" not in n["title"]]
        pool = sorted(pool, key=lambda n: -float(n.get("size_kb") or 0))
        notes = pool[offset:offset + top] if offset else pool[:top]
    elif offset:
        notes = notes[offset:]
    if limit:
        notes = notes[:limit]
    print(f"待处理 {len(notes)} 篇（关键词「{keyword or '（全部）'}」）…")
    index = core.build_link_index(cfg)
    pattern = core.compile_link_pattern(index)
    generic_skip = core.link_skip_words(cfg)
    changed, total_links, red_total = 0, 0, 0
    red_all: list = []

    def do_ai(n: dict, idx: int) -> dict:
        """处理一篇（AI 模式）；只返回结果，打印交给主线程，避免并发时输出交错。"""
        try:
            r = core.link_keywords_ai(cfg, Path(n["path"]), dry_run=not apply,
                                      red_links=red_links, first_only=first_only,
                                      skip_headings=skip_headings, max_links=max_links,
                                      max_red=max_red)
        except Exception as exc:                        # 单篇失败不影响整批
            r = {"ok": False, "report": [f"{type(exc).__name__}: {exc}"], "added": [], "red": []}
        return {"note": n, "idx": idx, "r": r}

    if use_ai and workers > 1:
        from concurrent.futures import ThreadPoolExecutor, as_completed
        print(f"   并发 {workers} 篇同时识别（共 {len(notes)} 篇）…")
        done = 0
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(do_ai, n, i) for i, n in enumerate(notes, 1)]
            for fut in as_completed(futures):
                item = fut.result()
                done += 1
                n, r = item["note"], item["r"]
                added, red = r.get("added") or [], r.get("red") or []
                print(f"   [{done}/{len(notes)}] {n['dir']}/{n['title']} → "
                      f"{len(added)} 个链接" + (f"｜待建 {len(red)}" if red else ""))
                if not added and not red:
                    continue
                changed += 1
                total_links += len(added)
                red_total += len(red)
                red_all.extend(red)
                if changed <= 25:
                    print("      " + "、".join(f"[[{a}]]" for a in added[:10])
                          + ("…" if len(added) > 10 else ""))
        notes = []                                       # 已在本轮处理完

    for i, n in enumerate(notes, 1):
        p = Path(n["path"])
        if use_ai:
            if i % 10 == 1 or i == len(notes):
                print(f"   …AI 识别中 {i}/{len(notes)}：{n['dir']}/{n['title']}")
            r = core.link_keywords_ai(cfg, p, dry_run=not apply, red_links=red_links,
                                      first_only=first_only, skip_headings=skip_headings,
                                      max_links=max_links, max_red=max_red)
            added, red = r.get("added") or [], r.get("red") or []
            if not added and not red:
                continue
        else:
            try:
                text = p.read_text(encoding="utf-8")
            except Exception:
                continue
            new_text, added = core.link_keywords_in_text(
                text, index, self_title=p.stem, first_only=first_only,
                skip_headings=skip_headings, max_links=max_links, pattern=pattern,
                skip_titles=generic_skip | core.note_own_names(cfg, p))
            red = []
            if not added:
                continue
            if apply and new_text.strip() != text.strip():
                core.backup_note(p, kb)
                core.write_text_keep_eol(p, new_text)
        changed += 1
        total_links += len(added)
        red_total += len(red)
        red_all.extend(red)
        if changed <= 25:
            print(f"· {n['dir']}/{n['title']}.md → {len(added)} 个：" +
                  "、".join(f"[[{a}]]" for a in added[:8]) + ("…" if len(added) > 8 else "")
                  + (f"｜待建 {len(red)} 个" if red else ""))
    if changed > 25:
        print(f"（其余 {changed - 25} 篇略）")
    print(f"\n{'已补' if apply else '可补'}双链：{changed} 篇、共 {total_links} 个链接"
          f"（候选写法 {len(index)} 个）")
    if red_all:
        uniq = sorted(set(red_all), key=lambda x: -red_all.count(x))
        print(f"待建词条（库内还没有，共 {len(set(red_all))} 个，按出现篇数排序前 30）："
              + "、".join(uniq[:30]))
    if not apply and changed:
        print("确认无误后加 --apply 写盘（每篇写前自动备份到 _备份/笔记/）。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
