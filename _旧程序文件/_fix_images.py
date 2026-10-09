# -*- coding: utf-8 -*-
"""
_fix_images.py —— 给词条批量配图（本地图库优先，其次中文维基百科，带作者/许可署名）。

规则（格式规范 §4）：
  * 图片存进 `Assets（图片地图）/词条名.jpg`；
  * 首图紧跟 H1，第二张起放 `## 🖼️ 相关图片`（`**关联**` 页脚之前）；
  * 联网取的图带一行 `> 图片来源：中文维基百科 / Wikimedia Commons · 作者：… · 许可：…`；
  * 已经有图的词条默认跳过（--force 可强制补）；
  * 查不到图/下载失败只记进报告，不写坏笔记。

安全措施：
  * 默认 **dry-run**：只打印"会配哪张图 / 哪些查不到"，不联网下载、不改文件；
  * `--apply` 才联网下载并写笔记，写前把每篇笔记备份到 `_备份/笔记/`（统一备份目录，同名只留最新一份）；
  * `--limit N` 只处理前 N 篇（先小批量试水）。

用法：
    py _fix_images.py                    # 预览（默认 02 人物图谱）
    py _fix_images.py --apply --limit 5  # 先给 5 篇配图看效果
    py _fix_images.py --apply            # 全量
    py _fix_images.py --dir "12 事件数据库 ⭐" --apply
"""
from __future__ import annotations

import re
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import core

SKIP_DIR_PARTS = ("templates", "模板", "assets", "attachments", "附件", "资产", "图片")
EMBED_RE = re.compile(r"!\[\[")



def iter_notes(root: Path, only_dir: str = ""):
    dirs = [root / only_dir] if only_dir else sorted(p for p in root.iterdir() if p.is_dir())
    for d in dirs:
        if not d.is_dir() or any(k in d.name.lower() for k in SKIP_DIR_PARTS):
            continue
        for p in sorted(d.glob("*.md")):
            if p.stem != "索引":
                yield p


def _entity_hints(path: Path, limit: int = 3) -> list:
    """正文里前几个 [[双链]] 实体，作为取图的备用检索词。

    时间线类词条标题是自造的（`1888年-北洋水师成军`），维基没有对应条目；
    退一步用条目里链接的实体（北洋水师 / 李鸿章…）取图，比空着强。
    """
    try:
        links = core.extract_links(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    out = []
    for name in links:
        clean = core.sanitize_title(name)
        if clean and clean not in out and not re.match(r"^\d+\s*", clean):
            out.append(clean)
    return out[:limit]


def _image_matches_title(file_name: str, title: str, hints: list | None = None) -> bool:
    """写盘前的安全检查：图片文件名必须与词条名同源，或命中词条里链接的实体。

    这条是为了防止「匹配逻辑写错时把同一张图塞进所有词条」这类事故：
    只认「同名 / 互为前缀」，或名字正好等于词条正文里链接的实体（如
    `1928年-东北易帜` 用 `张学良.jpg`——张学良确实在这条词条里被链接）。
    """
    stem = core.sanitize_title(Path(str(file_name)).stem)
    key = core.sanitize_title(title)
    if not stem or not key:
        return False
    if stem == key or stem.startswith(key) or key.startswith(stem):
        return True
    return stem in {core.sanitize_title(str(h)) for h in (hints or [])}


def main() -> int:
    args = list(sys.argv[1:])
    apply_ = "--apply" in args
    force = "--force" in args
    args = [a for a in args if a not in ("--apply", "--force")]
    limit = 0
    if "--limit" in args:
        i = args.index("--limit")
        if i + 1 < len(args):
            limit = int(args[i + 1])
            del args[i:i + 2]
    workers = 2
    if "--workers" in args:
        i = args.index("--workers")
        if i + 1 < len(args):
            workers = max(1, min(8, int(args[i + 1])))
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

    cfg = core.load_config()
    local_index = core.build_image_index(cfg)

    print("=" * 74)
    scope = only_dir or "全部内容目录（跳过 00 首页）"
    print(f"批量配图（{'联网下载并写盘' if apply_ else '预览（不联网、不改文件）'}）：{root} / {scope}")
    print("=" * 74)

    notes, skipped_module = [], 0
    for p in iter_notes(root, only_dir):
        if not only_dir and "首页" in p.parent.name:
            continue                                  # 首页不算词条
        norm = re.sub(r"^\d+\s*", "", p.parent.name).replace(" ⭐", "").replace("（中文）", "").strip()
        stem_norm = re.sub(r"^\d+\s*", "", core.sanitize_title(p.stem))
        if stem_norm == norm or stem_norm == norm.replace(" ", "") or stem_norm == norm.replace(" ", "").rstrip("）"):
            skipped_module += 1                       # 目录总览笔记（如 04军队与军事院校.md）不是词条
            continue
        notes.append(p)

    todo, has_image, local_hit = [], 0, []
    for p in notes:
        text = p.read_text(encoding="utf-8")
        if EMBED_RE.search(text) and not force:
            has_image += 1
            continue
        fields, _body = core.split_frontmatter(text)
        aliases = []
        if isinstance(fields, dict):
            for key in ("aliases", "别名", "别称", "title"):
                val = fields.get(key)
                if isinstance(val, list):
                    aliases.extend(str(x) for x in val)
                elif val:
                    aliases.append(str(val))
        found = core.match_images(local_index, p.stem, aliases, min_score=70)
        if found:
            local_hit.append((p, found[0]))
        else:
            todo.append((p, aliases + _entity_hints(p)))
    if limit:
        todo = todo[:limit]
        local_hit = local_hit[:limit]

    total_before = len(notes)
    print(f"词条总数：{total_before}　已有配图跳过：{has_image}　目录总览笔记跳过：{skipped_module}")
    print(f"本地图库可直接配：{len(local_hit)}　需要联网取图：{len(todo)}")

    planned, failed = list(local_hit), []
    if todo and apply_:
        from concurrent.futures import ThreadPoolExecutor, as_completed

        def _fetch(note: Path, hints: list):
            time.sleep(0.15)                          # 对图源客气一点，别触发限流
            return core.acquire_image(cfg, note.stem, hints)

        print(f"开始联网取图（{workers} 个并发线程，失败会自动退避重试）…")
        done = 0
        with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
            futures = {pool.submit(_fetch, p, aliases): p for p, aliases in todo}
            for fut in as_completed(futures):
                p = futures[fut]
                done += 1
                try:
                    res = fut.result()
                except Exception as exc:                     # 理论上 acquire_image 不抛
                    res = {"ok": False, "note": f"{type(exc).__name__}: {exc}"}
                if res.get("ok"):
                    planned.append((p, res))
                    print(f"  [{done}/{len(todo)}] ✓ {p.stem} → {res['file']}")
                else:
                    failed.append((p.stem, res.get("note", "")))
                    print(f"  [{done}/{len(todo)}] ✗ {p.stem}：{res.get('note')}")
    elif todo:
        print("（预览模式不联网：下面只列前 30 个待取图的词条）")
        print("    " + "、".join(p.stem for p, _a in todo[:30]) + ("…" if len(todo) > 30 else ""))

    if not apply_:
        print("-" * 74)
        print(f"预览结束：可配 {len(local_hit)} 篇（本地）+ 待联网 {len(todo)} 篇。")
        print("加 --apply 执行（下载 + 逐篇备份后写入）；加 --limit 5 可先试 5 篇。")
        return 0

    written, suspicious = 0, []
    backed = 0
    for p, entry in planned:
        if not _image_matches_title(entry.get("file", ""), p.stem, _entity_hints(p)):
            suspicious.append((p.stem, entry.get("file", "")))
            continue                                  # 安全检查：名字不同源就不写
        text = p.read_text(encoding="utf-8")
        new_text = core.insert_images(text, [entry])
        if new_text == text:
            continue
        if core.backup_note(p, root) is not None:      # 统一备份：_备份/笔记/<相对路径>（只留最新）
            backed += 1
        p.write_text(new_text, encoding="utf-8")
        written += 1
    if suspicious:
        print(f"安全检查拦下 {len(suspicious)} 条（图片名与词条名不同源，未写入）：")
        for name, fname in suspicious[:20]:
            print(f"    {name} ← {fname}")
    print("-" * 74)
    print(f"已配图写入 {written} 篇（原文件备份到 {core.BACKUP_DIR_NAME}/笔记/，共 {backed} 篇，只留最新）")
    if failed:
        out_list = Path(__file__).resolve().parent / "_未配图清单.txt"
        lines = ["未配到图的词条（可手动下载图片，按「词条名.后缀」放进 Assets（图片地图）/ 后重跑本脚本）",
                 "=" * 60]
        lines += [f"{name}\t{why}" for name, why in sorted(failed)]
        out_list.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"查不到图/下载失败 {len(failed)} 篇 → 清单：{out_list}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
