# -*- coding: utf-8 -*-
"""
_整理备份.py —— 把散落的 `_备份_*` 目录统一整理进 `_备份/`，每个文件只保留最新一份。

新目录约定（程序所有备份都写这里）：
    _备份/模板/<模板名>.md                 模板被覆盖前的旧版（只留最新）
    _备份/笔记/<知识库相对路径>/<文件>.md     笔记被改写前的旧版（只留最新）
    _备份/快照/<时间戳>-<名称>/…            整库级操作前的快照，只保留最近 3 份

用法：
    py _整理备份.py                 # 预览（不动任何文件）
    py _整理备份.py --apply         # 真的整理：复制 → 校验 → 删除旧目录
    py _整理备份.py --keep-old      # --apply 时保留旧目录（只复制不删）
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

import core

HERE = Path(__file__).resolve().parent
SKIP_TOP = ("19民国", "民国历史知识库", "_备份")      # 旧备份里多余的层级 / 新备份根自身


def kind_of(dirname: str) -> str:
    return "模板" if "模板" in dirname else "笔记"


def strip_leading(rel: Path) -> Path:
    parts = list(rel.parts)
    while parts and parts[0] in SKIP_TOP:
        parts.pop(0)
    return Path(*parts) if parts else Path(rel.name)


def iter_sources() -> list:
    out = []
    for base in (HERE, HERE.parent):
        for d in sorted(base.glob("_备份_*")):
            if d.is_dir() and d not in out:
                out.append(d)
    return out


def plan(sources: list) -> tuple:
    """算出每个文件该落到哪、哪些因为已有（或计划中）更新的副本而跳过。

    注意：预览阶段磁盘上还没有任何新副本，所以必须同时跟"计划里已有的目标"比较，
    否则同一个文件的多份旧备份会被全部算成新增。
    """
    planned: dict = {}          # 目标路径 → (源文件, 目标, kind, mtime, 目标原本是否已存在)
    stats = {"files": 0, "new": 0, "overwrite": 0, "keep": 0, "by_dir": {}}
    for src in sources:
        kind = kind_of(src.name)
        n_take = n_skip = 0
        for f in sorted(src.rglob("*")):
            if not f.is_file():
                continue
            dest = core.backup_root() / kind / strip_leading(f.relative_to(src))
            key = str(dest)
            stats["files"] += 1
            mt = f.stat().st_mtime
            prev = planned.get(key)
            newest = max([m for m in ((prev[3] if prev else None),
                                      (dest.stat().st_mtime if dest.exists() else None))
                          if m is not None], default=None)
            if newest is None or mt > newest:
                planned[key] = (f, dest, kind, mt,
                                dest.exists() if prev is None else prev[4])
                n_take += 1
            else:
                n_skip += 1
        stats["by_dir"][src.name] = (n_take, n_skip)
    stats["new"] = sum(1 for v in planned.values() if not v[4])
    stats["overwrite"] = len(planned) - stats["new"]
    stats["keep"] = stats["files"] - len(planned)
    todo = [v[:3] for v in sorted(planned.values(), key=lambda v: str(v[1]))]
    return todo, stats


def write_readme() -> None:
    root = core.backup_root()
    (root / "说明.md").write_text(
        "# 备份目录说明（程序自动维护）\n\n"
        "程序的所有备份都放在这里，命名固定，**每个文件只保留最新一份**：\n\n"
        "| 子目录 | 内容 | 保留策略 |\n"
        "| --- | --- | --- |\n"
        "| `模板/` | 模板被覆盖前的旧版（同步模板 / 修复模板时） | 同名覆盖，每个模板只留最新 |\n"
        "| `笔记/` | 笔记被改写前的旧版，按知识库目录结构存放 | 同名覆盖，每篇笔记只留最新 |\n"
        "| `快照/` | 整库级操作（批量迁移等）前的快照 | 只保留最近 "
        f"{core.BACKUP_KEEP_SNAPSHOTS} 份，自动清理 |\n\n"
        "恢复某一篇：把 `笔记/<目录>/<文件>.md` 复制回知识库同路径即可。\n\n"
        "整理旧备份：`py _整理备份.py`（预览）→ `py _整理备份.py --apply`。\n",
        encoding="utf-8")


def main() -> int:
    apply = "--apply" in sys.argv
    keep_old = "--keep-old" in sys.argv
    core.backup_root()                                   # 建好 _备份/
    sources = iter_sources()
    if not sources:
        print("没有发现散落的 _备份_* 目录（已整理过）")
        write_readme()
        return 0

    print(f"发现 {len(sources)} 个旧备份目录：")
    todo, stats = plan(sources)
    for name, (a, b) in stats["by_dir"].items():
        print(f"   {name:<46} 采纳 {a:<5} 跳过较旧 {b}")
    print(f"\n合计 {stats['files']} 个文件 → 去重后保留 {len(todo)} 份"
          f"（其中新增 {stats['new']}、覆盖同名旧备份 {stats['overwrite']}），"
          f"丢弃较旧副本 {stats['keep']} 份")
    print(f"统一目录：{core.backup_root()}")

    if not apply:
        print("\n（预览模式，未改动任何文件；加 --apply 执行）")
        return 0

    done = 0
    for src, dest, _kind in todo:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        done += 1
    print(f"\n已复制 {done} 个文件到 _备份/")

    # 校验：旧目录里每个文件都要在新目录里有对应副本，且不能比旧文件更旧
    # （新目录里是同名"最新版"：时间戳相同=同一份，更新=故意保留了更新的版本；只有更旧才算丢）
    missing = []
    for src in sources:
        kind = kind_of(src.name)
        for f in src.rglob("*"):
            if not f.is_file():
                continue
            dest = core.backup_root() / kind / strip_leading(f.relative_to(src))
            if not dest.exists():
                missing.append(str(dest))
                continue
            same = abs(dest.stat().st_mtime - f.stat().st_mtime) < 1.0
            if same and dest.stat().st_size != f.stat().st_size:
                missing.append(str(dest))          # 同一版本却大小不符 → 复制有问题
            elif dest.stat().st_mtime < f.stat().st_mtime - 1.0:
                missing.append(str(dest))          # 新目录里的反而更旧 → 不能删旧的
    if missing:
        print(f"⚠ 有 {len(missing)} 个文件在新目录里对不上，为安全起见**不删除**旧目录：")
        for m in missing[:10]:
            print("   " + m)
        return 1

    if keep_old:
        print("校验通过（--keep-old：旧目录保留，可自行删除）")
    else:
        for src in sources:
            shutil.rmtree(src, ignore_errors=True)
        print(f"校验通过，已删除 {len(sources)} 个旧备份目录")
    write_readme()
    summary = core.backup_summary()
    print("整理后：" + "、".join(f"{k} {v['files']} 个文件/{v['mb']} MB"
                                 for k, v in summary.items() if isinstance(v, dict)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
