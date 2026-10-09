# -*- coding: utf-8 -*-
"""
_check_format.py —— 只读检查工具（**不改动任何文件**）。两种用法：

1) `--syntax`：**Markdown 结构体检（语法体检）**，纯文本判定、零 token。逐项报告 7 类"语法级污染"：
   ```
   === Markdown 结构体检 ===
   [[_索引|X]]        : 0        ✅
   嵌套双链           : 0        ✅
   <!-- 不配对        : 0        ✅
   frontmatter 异常   : 0        ✅
   BOM 文件           : 0        ✅
   同文件重复 ##      : 3        ⚠️  谢安.md(⚖️历史评价×2) ...
   ```
   有问题时退出码非 0（便于脚本化）；全绿退出码 0。

2) 不带 `--syntax`：老的"模板 vs 笔记"格式差异报告（字段/小节差异、风格分布）。

用法：
    py _check_format.py --syntax              # 体检当前知识库（config.json 的 knowledge_base）
    py _check_format.py --syntax "<库名或路径>"   # 指定库/目录（相对知识库 或 绝对路径 都行）
    py _check_format.py --syntax --limit 30   # 只抽查前 30 篇
    py _check_format.py --syntax --json       # 机器可读（GUI/脚本用）
    py _check_format.py --quality             # 规范清单体检：读规范 §15，逐条报 自动/人工/未通过/脱节
    py _check_format.py --quality "<库名或路径>"  # 指定库；--json 可机器读
    py _check_format.py --mine-types          # 类型关键词挖掘：只读预览「建议新增哪些类型关键词」
    py _check_format.py --mine-types "06-02两晋" --json   # 指定库 / 机器可读（写入由 GUI ② 页确认后做）
    py _check_format.py --audit-types         # 类型判定体检：拿库里已有笔记名当标准答案，量准确率 + 判错清单 + 建议关键词
    py _check_format.py --audit-types "06-04十六国南北朝"  # 指定库（退出码：全对 0 / 有错判 1 / 路径不存在 2）
    py _check_format.py                        # 老的格式差异报告
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

import core

try:
    KB = Path(core.resolve_kb(core.load_config()))    # 默认跟随 ①页当前知识库（不再写死某个库）
except Exception:
    KB = Path(".")
SKIP_DIR_PARTS = ("Templates", "模板", "assets", "附件", "资产")


# ----------------------------------------------------------------------
# 通用小工具
# ----------------------------------------------------------------------
def tpl_dir() -> Path | None:
    """当前生效的模板库（跟着 config / 知识库走）。"""
    try:
        return core.templates_dir(core.load_config())
    except Exception:
        return None


def parse_fm_fields(text: str) -> list:
    """返回 frontmatter 顶层字段名列表（有则解析，无则空）。"""
    fields, _ = core.split_frontmatter(text)
    if fields is None:
        return []
    return list(fields.keys())


def parse_h2_sections(text: str) -> list:
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


# ----------------------------------------------------------------------
# ① 语法体检
# ----------------------------------------------------------------------
def _resolve_path(path):
    """把「绝对路径 / 知识库内相对路径 / 与知识库同级的目录名」解析成真实路径（不存在返回 None）。"""
    if not path:
        return True
    q = Path(str(path))
    if not q.is_absolute():
        kb = core.resolve_kb(core.load_config())
        cands = []
        if kb:
            base = kb
            for _ in range(3):
                cands.append(base / str(path))
                base = base.parent
        cands.append(q)
        q = next((c for c in cands if c.exists()), q)
    return q if q.exists() else None


def quality_cli(path=None, limit: int = 0, as_json: bool = False) -> int:
    """跑「规范清单体检」并打印；返回退出码（有未通过或脱节 → 1，否则 0）。"""
    cfg = core.load_config()
    if path:
        rp = _resolve_path(path)
        if rp is None:
            print("✗ 路径不存在：" + str(path))
            print("   （可给绝对路径，或给「知识库内相对路径」或「与知识库同级的目录名」，如「06-02两汉」）")
            return 2
        cfg = dict(cfg)
        cfg["knowledge_base"] = str(rp)
    res = core.quality_checklist(cfg, limit=limit)
    if as_json:
        print(json.dumps(res, ensure_ascii=False, indent=1))
        return 0 if res.get("ok") else 1
    total = res["total"]
    mapped = res["mapped"]
    failed = res["failed"]
    manual = res["manual"]
    passed = mapped - failed
    spec_name = Path(res["spec_path"]).name if res.get("spec_path") else "（未找到规范）"
    print("=== 规范清单体检（来源：" + spec_name + " · " + core.SPEC_SECTION_HEAD
          + "，共 " + str(total) + " 条）===")
    if not total:
        print("⚠️  没有找到规范文件或缺 §15 一节；可在 config.json 里用 spec_url/spec_file 指定规范路径。")
        for d in res.get("drift", []):
            print("   · " + d)
        return 1
    print("自动检查：" + str(mapped) + " 条（通过 " + str(passed) + " / 未通过 " + str(failed) + "）"
          + "｜人工复核：" + str(manual) + " 条｜扫描 " + str(res["scan_files"]) + " 篇笔记")
    print()
    icons = {"pass": "✅", "fail": "❌", "manual": "⚪"}
    for r in res["items"]:
        text = r["text"]
        if len(text) > 44:
            text = text[:44]
        line = icons[r["status"]] + " " + str(r["no"]).rjust(2) + ". " + text.ljust(46)
        if r["status"] == "fail":
            line += "→ 未通过（" + r["detail"][:90] + "）"
        elif r["status"] == "manual":
            line += "→ 人工复核"
        else:
            line += "→ 通过"
            if r.get("detail"):
                line += "（" + r["detail"] + "）"
        print(line)
    if res["drift"]:
        print()
        print("⚠️  脱节（规范有变化，请复核映射表 SPEC_QUALITY_MAP）：")
        for d in res["drift"]:
            print("   · " + d)
    print()
    if res.get("ok"):
        print("✅ 规范清单：全部自动检查通过、无脱节。")
    else:
        print("⚠️  上面标 ❌ / 脱节 的项需要处理（本工具只报告、不修改任何文件）。")
    return 0 if res.get("ok") else 1


def syntax_cli(path=None, limit: int = 0, as_json: bool = False) -> int:
    """跑 7 项 Markdown 结构体检并打印；返回退出码（全绿 0，有问题 1）。"""
    paths = None
    if path:
        p = Path(str(path))
        if not p.is_absolute():
            kb = core.resolve_kb(core.load_config())
            cands = []
            if kb:
                base = kb
                for _ in range(3):                     # 依次试：知识库内 / 上级 / 再上级（历史 根）
                    cands.append(base / str(path))
                    base = base.parent
            cands.append(p)
            p = next((c for c in cands if c.exists()), p)
        if not p.exists():
            print(f"✗ 路径不存在：{p}")
            print("   （可给绝对路径，或给「知识库内相对路径」或「与知识库同级的目录名」，如「06-02两汉」）")
            return 2
        paths = [p]
    res = core.syntax_check(paths=paths, limit=limit)
    if as_json:
        print(json.dumps({"files": res["files"], "ok": res["ok"], "counts": res["counts"],
                          "findings": res["findings"], "roots": res["roots"]},
                         ensure_ascii=False, indent=1))
        return 0 if res["ok"] else 1
    counts, findings = res["counts"], res["findings"]
    print("=== Markdown 结构体检 ===")
    print(f"检查 {res['files']} 篇" + (f"（来源：{res['roots'][0]}）" if res.get("roots") else ""))
    for key, label in core.SYNTAX_ITEMS:
        n = counts.get(key, 0)
        mark = "✅" if n == 0 else "⚠️"
        extra = ""
        if n:
            extra = "  " + "；".join(str(x) for x in findings.get(key, [])[:6])
            if n > len(findings.get(key, [])):
                extra += f"；…（其余 {n - len(findings.get(key, []))} 处略）"
        print(f"{label:<18}: {n:<8}{mark}{extra}")
    print()
    if res["ok"]:
        print("✅ 七项全绿：没有发现语法级问题。")
    else:
        print("⚠️  发现下列问题（本工具**只报告、不修改任何文件**）：")
        for key, label in core.SYNTAX_ITEMS:
            if not counts.get(key):
                continue
            print(f"\n--- {label}（{counts[key]} 处）---")
            for it in findings.get(key, [])[:20]:
                print("   · " + str(it))
    return 0 if res["ok"] else 1


# ----------------------------------------------------------------------
# ② 老的"模板 vs 笔记"格式差异报告
# ----------------------------------------------------------------------
def main_diff(kb=None) -> None:
    """打印"模板 vs 笔记"的格式差异报告（只读）。"""
    global KB
    if kb:
        p = Path(str(kb))
        if not p.is_absolute():
            root = core.resolve_kb(core.load_config())
            p = (root / str(kb)) if root else p
        KB = p
    td = tpl_dir()
    if td is None or not Path(td).is_dir():
        print("模板目录不存在（④页可指定模板库；或改 config.json 的 templates_dir）：", td)
        return
    TPL_DIR = Path(td)

    # 1. 解析所有模板
    templates: dict = {}
    for tp in sorted(TPL_DIR.glob("*.md")):
        text = tp.read_text(encoding="utf-8")
        templates[tp.stem] = (parse_fm_fields(text), parse_h2_sections(text), template_style(text))

    print("=" * 70)
    print("一、模板清单（字段数 / 小节数 / 风格）")
    print("=" * 70)
    for name, (fm, h2, style) in templates.items():
        print(f"  {name:<14} frontmatter {len(fm):>2} 字段 | 正文 {len(h2):>2} 小节 | {style}")

    # 2. 目录 → 模板 映射（emoji 型目录同名优先）
    cfg = core.load_config()
    routes = cfg.get("routes", {})
    dir2tpl: dict = {}
    for tp_dir in sorted(KB.iterdir()):
        if not tp_dir.is_dir():
            continue
        dname = tp_dir.name
        norm = re.sub(r"^\d+\s*", "", dname).replace(" ⭐", "").replace("（中文）", "").strip()
        if norm in templates and templates[norm][2] == "emoji型":
            dir2tpl[dname] = norm
            continue
        ttype = next((t for t, d in routes.items()
                      if core.normalize_dir_name(d) == core.normalize_dir_name(dname)), None)
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
        for md in sorted(tp_dir.rglob("*.md")):
            if md.stem in ("索引", "_索引") or core._is_skipped_path(md):
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
                detail.append((dname, md.stem, actual_style,
                               "、".join(fm_miss) or "无", "、".join(h2_miss) or "无",
                               "、".join(fm_extra) or "无", "、".join(h2_extra) or "无"))
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


def mine_cli(path=None, as_json: bool = False, min_count: int = 3) -> int:
    """跑「类型关键词挖掘」并打印（**只报告，绝不写配置**）。"""
    cfg = core.load_config()
    if path:
        rp = _resolve_path(path)
        if rp is None:
            print("✗ 路径不存在：" + str(path))
            print("   （可给绝对路径，或给「知识库内相对路径」或「与知识库同级的目录名」，如「06-02两晋」）")
            return 2
        kb = Path(rp)
        prof = core.get_kb_profile(cfg, kb)
        cfg = dict(cfg)
        cfg["knowledge_base"] = str(kb)
        if prof.get("routes"):
            cfg["routes"] = prof["routes"]
        for k in ("template_routes", "type_keywords", "footer_types", "templates_dir"):
            if prof.get(k) is not None:
                cfg[k] = prof[k]
    res = core.preview_type_keywords(cfg, min_count=min_count)
    if as_json:
        print(json.dumps(res, ensure_ascii=False, indent=1))
        return 0
    print("=== 类型关键词挖掘（只读预览；**不改任何配置**）===")
    print("知识库：" + str(res.get("kb") or "（未设置）") + "｜扫描 " + str(res.get("scanned", 0)) + " 篇笔记")
    if res.get("note"):
        print("⚠️  " + str(res["note"]))
        return 1
    print()
    for line in res["lines"]:
        print(line)
    if res.get("dropped"):
        print()
        print("被丢弃的候选（前 12 条）：")
        for d in res["dropped"][:12]:
            print("   · " + str(d.get("type")) + "｜" + str(d.get("word")) + "（" + str(d.get("count"))
                  + " 次）→ " + str(d.get("why")))
    print()
    print("写入方式：GUI ② 页点「⛏ 重挖类型关键词」→ 预览 → 你确认后才写入该库档案（只增不减）。")
    return 0


def audit_cli(path=None, limit: int = 0, as_json: bool = False) -> int:
    """跑「类型判定体检」并打印（**只读**：拿库里已有笔记名当标准答案，量准确率）。

    退出码：全部判对 → 0；有错判/判不出 → 1；路径不存在 → 2。
    """
    cfg = core.load_config()
    kb = None
    if path:
        rp = _resolve_path(path)
        if rp is None:
            print("✗ 路径不存在：" + str(path))
            print("   （可给绝对路径，或给「知识库内相对路径」或「与知识库同级的目录名」，如「06-03两晋」）")
            return 2
        kb = Path(rp)
    res = core.audit_type_keywords(cfg, kb=kb, limit=limit)
    if as_json:
        print(json.dumps(res, ensure_ascii=False, indent=1))
        return 1 if res.get("wrong") else 0
    if res.get("note"):
        print("⚠️  " + str(res["note"]))
        return 1
    total, correct = res.get("total", 0), res.get("correct", 0)
    wrong = res.get("wrong") or []
    blank = res.get("blank", 0)
    print("=== 类型判定体检（只读；拿库里每个类型目录下的已有笔记名当标准答案）===")
    print("知识库：" + str(res.get("kb") or "（未设置）"))
    _blank_txt = f"；其中判不出 {blank} 篇" if blank else ""
    print(f"准确率 {res.get('accuracy', 0) * 100:.1f}%（对 {correct} / 错 {len(wrong)}，共 {total} 篇{_blank_txt}）")
    if wrong:
        print()
        print(f"--- 判错的（前 30 条，共 {len(wrong)} 条）---")
        for w in wrong[:30]:
            print(f"   · {w['name']}  应在「{w['expected']}」→ 实判「{w['guessed'] or '（判不出）'}」"
                  f"   {w.get('file', '')}")
        if len(wrong) > 30:
            print(f"   …（其余 {len(wrong) - 30} 条略；用 --json 看全部）")
    sg = res.get("suggest") or {}
    print()
    if sg:
        print("--- 从错判里归纳的建议关键词（可到 ②页「⛏ 重挖类型关键词」或 GUI「🩺 类型判定体检」写入该库档案）---")
        for t, spec in sg.items():
            if isinstance(spec, dict):
                if spec.get("strong"):
                    print(f"   [{t}] 强匹配：{'、'.join(spec['strong'])}")
                if spec.get("fallback"):
                    print(f"   [{t}] 兜底：{'、'.join(spec['fallback'])}")
            else:
                print(f"   [{t}] {'、'.join(spec)}")
    else:
        print("（没有可归纳的建议关键词：错判太少或前缀会与其他类型冲突，宁少不误吞 ✓）")
    print()
    print("说明：本命令**只报告、不写任何配置**。要写入建议：GUI ② 页「🩺 类型判定体检」→ 预览 → 你点「写入」。")
    return 1 if wrong else 0


def main(argv=None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])
    if "--audit-types" in args:
        i = args.index("--audit-types")
        path = None
        if i + 1 < len(args) and not args[i + 1].startswith("--"):
            path = args[i + 1]
        limit = 0
        if "--limit" in args:
            j = args.index("--limit")
            if j + 1 < len(args):
                try:
                    limit = int(args[j + 1])
                except ValueError:
                    limit = 0
        return audit_cli(path, limit, "--json" in args)
    if "--mine-types" in args:
        i = args.index("--mine-types")
        path = None
        if i + 1 < len(args) and not args[i + 1].startswith("--"):
            path = args[i + 1]
        mc = 3
        if "--min-count" in args:
            j = args.index("--min-count")
            if j + 1 < len(args):
                try:
                    mc = max(1, int(args[j + 1]))
                except ValueError:
                    mc = 3
        return mine_cli(path, "--json" in args, mc)
    if "--quality" in args:
        i = args.index("--quality")
        path = None
        if i + 1 < len(args) and not args[i + 1].startswith("--"):
            path = args[i + 1]
        limit = 0
        if "--limit" in args:
            j = args.index("--limit")
            if j + 1 < len(args):
                try:
                    limit = int(args[j + 1])
                except ValueError:
                    limit = 0
        return quality_cli(path, limit, "--json" in args)
    if "--syntax" in args:
        i = args.index("--syntax")
        path = None
        if i + 1 < len(args) and not args[i + 1].startswith("--"):
            path = args[i + 1]
        limit = 0
        if "--limit" in args:
            j = args.index("--limit")
            if j + 1 < len(args):
                try:
                    limit = int(args[j + 1])
                except ValueError:
                    limit = 0
        return syntax_cli(path, limit, "--json" in args)
    positional = [a for a in args if not a.startswith("--")]
    main_diff(positional[0] if positional else None)
    return 0


if __name__ == "__main__":
    sys.exit(main())
