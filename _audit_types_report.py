# -*- coding: utf-8 -*-
"""
_audit_types_report.py —— 类型判定体检报告生成器（**只读**，零 token）

用法：
    py _audit_types_report.py                 # 体检 config.json 里所有有档案的知识库 + 当前库
    py _audit_types_report.py <库路径> [<库路径> ...]
    py _audit_types_report.py --out "_报告\\类型判定体检.md"

原理：**库里每个类型目录下的已有笔记名就是标准答案**（`01人物\谢安.md` → 判定器也该判成「人物」）。
     跑一遍就能量出准确率、错在哪、该补哪些关键词 —— 换任何时期/朝代库，先跑一次就知道行不行。
输出：Markdown 报告（默认写 `<程序目录>\_报告\类型判定体检.md`）。**绝不修改任何知识库文件**。
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import core


def _libs_from_cfg(cfg: dict) -> list:
    """配置里有档案的知识库 + 当前库（去重，保持稳定顺序）。"""
    out: list = []
    cur = core.resolve_kb(cfg)
    if cur is not None:
        out.append(cur)
    for prof in (cfg.get("profiles") or {}).values():
        p = str((prof or {}).get("kb") or "").strip()
        if p and Path(p).is_dir():
            cand = Path(p)
            if all(str(cand) != str(x) for x in out):
                out.append(cand)
    return out


def build_report(libs: list) -> str:
    cfg = core.load_config()
    lines = ["# 类型判定体检报告", "",
             f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}（**只读**：未修改任何知识库文件、未写配置）",
             "",
             "原理：**库里每个类型目录下的已有笔记名就是标准答案** —— "
             "例如 `01人物\\谢安.md` 这个事实本身说明判定器也应该把「谢安」判成「人物」。",
             "",
             "> **换到别的朝代（宋/辽/金/元/明/清…）也这样自查**："
             "先把该库填进 ①页 → ②页点「🔎 扫描当前库目录生成类型」→ 跑 "
             "`py _check_format.py --audit-types <库>`（或 GUI ②页「🩺 类型判定体检」）→ "
             "看准确率与判错清单；建议关键词可直接在预览窗里一键并入该库档案（只增不减）。", ""]
    summary = []
    for kb in libs:
        r = core.audit_type_keywords(cfg, kb=kb)
        name = Path(str(r.get("kb") or kb)).name
        total, correct = r.get("total", 0), r.get("correct", 0)
        wrong = r.get("wrong") or []
        blank = r.get("blank", 0)
        acc = float(r.get("accuracy") or 0) * 100
        summary.append((name, total, correct, len(wrong), blank, acc))
        lines.append(f"## {name}")
        lines.append("")
        if r.get("note"):
            lines.append(f"⚠️ {r['note']}")
            lines.append("")
            continue
        _blank_txt = f"（其中「判不出」{blank} 篇）" if blank else ""
        lines.append(f"- 检查 **{total}** 篇：判对 **{correct}**｜判错 **{len(wrong)}**"
                     f"{_blank_txt}｜准确率 **{acc:.1f}%**")
        lines.append(f"- 类型数：{len(core._cfg_for_kb(cfg, kb).get('routes') or {})}"
                     f"｜扫描到的笔记：{r.get('scanned', 0)} 篇")
        lines.append("")
        if wrong:
            lines.append("### 判错清单（前 30 条）")
            lines.append("")
            lines.append("| 笔记 | 应在 | 实判 | 文件 |")
            lines.append("| --- | --- | --- | --- |")
            for w in wrong[:30]:
                lines.append(f"| {w['name']} | {w['expected']} | {w['guessed'] or '（判不出）'} | {w.get('file', '')} |")
            if len(wrong) > 30:
                lines.append(f"| … | 其余 {len(wrong) - 30} 条略 | | |")
            lines.append("")
            lines.append("> 「判不出」是**诚实行为**（判定器不猜）；"
                         "「判成别的类型」才可能是要补关键词，或**这篇笔记放错了目录**（两种都可能）。")
            lines.append(">")
            lines.append("> 注意：**多时段库**（比如把类型拆成 `人物-五胡十六国 / 人物-南朝 / 人物-北朝`）"
                         "会出现大量「判不出」—— 这是**设计上不猜**（说不清属于哪个时段）："
                         "请写成 `类型:名称`，或给该库配 `type_keywords`（GUI ②页「🛠 类型判定体检」可一键写入建议）。")
            lines.append("></br>另：若某个类型目录里**故意**混放了别的类别（例如把「运动」归在派系下），"
                         "那条会被记为「判错」—— 这是库的组织习惯，不是判定器错。")
            lines.append("")
        sg = r.get("suggest") or {}
        if sg:
            lines.append("### 从错判里归纳的建议关键词（可在 GUI ②页预览后一键写入该库档案，只增不减）")
            lines.append("")
            for t, spec in sg.items():
                if isinstance(spec, dict):
                    if spec.get("strong"):
                        lines.append(f"- **{t}** 强匹配：{'、'.join(spec['strong'])}")
                    if spec.get("fallback"):
                        lines.append(f"- **{t}** 兜底：{'、'.join(spec['fallback'])}")
                else:
                    lines.append(f"- **{t}**：{'、'.join(spec)}")
            lines.append("")
        else:
            lines.append("（没有可归纳的建议关键词：错判太少、或候选前缀会与其他类型冲突 —— 宁少不误吞 ✓）")
            lines.append("")
    lines.append("## 汇总")
    lines.append("")
    lines.append("| 知识库 | 篇数 | 判对 | 判错 | 判不出 | 准确率 |")
    lines.append("| --- | --- | --- | --- | --- | --- |")
    for name, total, correct, wn, blank, acc in summary:
        lines.append(f"| {name} | {total} | {correct} | {wn} | {blank} | {acc:.1f}% |")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 补充说明：判定规则的通用性（era-neutral）")
    lines.append("")
    lines.append("判定器**不预设任何时期词汇**，只按通用规则打分（A 强匹配 > C 概念 > B 兜底）：")
    lines.append("")
    lines.append("- **国号/政权**：整字国号（金/元/明/清/辽/梁…）+ 两字国号（东晋/前秦/冉魏/刘宋/胡夏…）"
                 "+ 政权专名白名单（高句丽/西夏/翟魏…）→ 该库「政权类」；")
    lines.append("- **时期名**（十六国/南北朝/五代十国/春秋/战国…）→ 该库有「时期/时代」类就用它，"
                 "没有就**诚实报「这是时期名」**（不硬塞成政权 ✗）；")
    lines.append("- **少数民族/外来姓名**（耶律/完颜/爱新觉罗/孛儿只斤/拓跋/慕容… + 日文姓氏如 乃木/冈村/土肥原…）→ 人物类；")
    lines.append("- **条约/盟约**（之盟/条约/和议…）→ 该库 条约 > 盟约 > 外交 > 邦交 > 史料 > 事件；")
    lines.append("- **姓氏**：百家姓全集 + 罕见历史姓氏 + 复姓（尔朱/乙弗/阿史那…）；**地名**：后缀 + 历史地名白名单，"
                 "且「姓氏+地名」判人名优先（孙中山 ✓）；")
    lines.append("- 还判不出的（如**五字以上外来人名** `耶律阿保机` 之外的生僻名、"
                 "**专题/论述类** `佛教的南传与本土化`、**时期名而本库无对应类型**）"
                 "→ 一律**诚实返回空并给提示**，请写成 `类型:名称` 或用 `type_keywords` 扩展。")
    lines.append("")
    return "\n".join(lines)


def main(argv=None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])
    out = core.app_dir() / "_报告" / "类型判定体检.md"
    if "--out" in args:
        i = args.index("--out")
        if i + 1 < len(args):
            out = Path(args[i + 1])
            if not out.is_absolute():
                out = core.app_dir() / out
            args = args[:i] + args[i + 2:]
    paths = [a for a in args if not a.startswith("--")]
    cfg = core.load_config()
    libs = [Path(p) for p in paths if Path(p).is_dir()] if paths else _libs_from_cfg(cfg)
    if not libs:
        print("✗ 没有可体检的知识库（config.json 里没有档案，也没给路径）")
        return 2
    text = build_report(libs)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(f"✓ 已生成报告：{out}")
    for line in text.splitlines():
        if line.startswith("| ") and "准确率" not in line and "---" not in line:
            print("   " + line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
