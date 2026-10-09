# -*- coding: utf-8 -*-
"""_snapshot.py —— 改代码前先把"将要改的文件"存成带时间戳的备份（纯标准库，零依赖）

背景（血泪教训）：近两轮有两次"改了代码却没留改前备份"，只能靠事后重建副本，
所以把这件事做成一条命令，子代理与人工改代码前都先跑它。

用法（在项目根目录下运行）：

    py _snapshot.py core.py gui.py _check_spec.py          # 备份这几个文件
    py _snapshot.py --list core.py gui.py                  # 只列将生成的目标路径，不复制
    py _snapshot.py --stamp 修复X core.py                  # 自定义时间戳（默认 YYYYMMDD_HHMMSS）

行为：
  * 每个参数必须是**项目根目录下的文件**（目录、通配符、项目外路径、不存在 → 报错并跳过，不做任何写操作）；
  * 复制到 `_旧程序文件\\<文件名>.bak_<时间戳>`；
  * 同名备份已存在 → 依次加 `_2`、`_3`…（**绝不覆盖旧备份**）；
  * 打印每个备份的完整路径，末尾给一行"怎么回退"；
  * 退出码：全部成功 0 / 有任何失败 1。

环境变量（测试用）：`SNAPSHOT_ROOT` 可覆盖"项目根"。
输出编码：中文 + UTF-8（与项目其它脚本一致；.bat 已 `chcp 65001`，命令行请设 PYTHONUTF8=1）。
"""

from __future__ import annotations

import os
import shutil
import sys
import time
from pathlib import Path

# ── 输出编码（与项目其它脚本一致）─────────────────────────────────────────────
try:  # pragma: no cover - 取决于运行环境
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
except Exception:
    pass

BAK_DIR_NAME = "_旧程序文件"

# 项目根：本脚本所在目录（可用 SNAPSHOT_ROOT 覆盖，便于测试）
ROOT = Path(os.environ.get("SNAPSHOT_ROOT") or Path(__file__).resolve().parent).resolve()


def _ts() -> str:
    return time.strftime("%Y%m%d_%H%M%S")


def _unique_target(bak_dir: Path, name: str, stamp: str) -> Path:
    """返回一个**尚不存在**的备份路径：<name>.bak_<stamp>、必要时 _2、_3…"""
    base = f"{name}.bak_{stamp}"
    cand = bak_dir / base
    i = 2
    while cand.exists():
        cand = bak_dir / f"{base}_{i}"
        i += 1
    return cand


def _resolve(arg: str) -> tuple[Path | None, str]:
    """把参数解析成"项目根下的文件"；不合法时返回 (None, 中文原因)。"""
    if not arg or arg.strip() == "":
        return None, "空参数"
    if any(ch in arg for ch in "*?[]"):
        return None, "看起来是通配符；请先把文件列出来（本工具不展开通配符）"
    p = Path(arg)
    if not p.is_absolute():
        # 相对路径优先按"项目根"解析（工具就是为在项目根下用而写的），
        # 根下找不到再退回当前工作目录，两者都没有 → 报"文件不存在"。
        cand = ROOT / p
        if not cand.exists() and (Path.cwd() / p).exists():
            cand = Path.cwd() / p
        p = cand
    try:
        p = p.resolve()
    except OSError as exc:
        return None, f"路径无法解析（{exc}）"
    if not p.exists():
        return None, "文件不存在"
    if p.is_dir():
        return None, "这是一个目录；本工具只备份单个文件（目录请自行打包/复制）"
    if not p.is_file():
        return None, "不是普通文件"
    try:
        p.relative_to(ROOT)
    except ValueError:
        return None, f"不在项目根内（项目根：{ROOT}）"
    if p.parent.name == BAK_DIR_NAME:
        return None, f"这已经在 {BAK_DIR_NAME}\\ 里了（不备份备份）"
    return p, ""


def main(argv: list[str]) -> int:
    args = list(argv)
    list_only = False
    stamp: str | None = None
    files: list[str] = []
    i = 0
    while i < len(args):
        a = args[i]
        if a in ("-h", "--help", "/?"):
            print(__doc__)
            return 0
        if a == "--list":
            list_only = True
        elif a == "--stamp":
            i += 1
            if i >= len(args):
                print("✗ --stamp 后面要跟一个时间戳文本，例如 --stamp 修复X")
                return 1
            stamp = args[i]
        elif a.startswith("-"):
            print(f"✗ 未知参数：{a}（用 --help 看用法）")
            return 1
        else:
            files.append(a)
        i += 1

    if not files:
        print("用法：py _snapshot.py <文件…>（可加 --list 只预览、--stamp <文本> 自定义时间戳）")
        print(f"项目根：{ROOT}")
        return 1

    stamp = stamp or _ts()
    bak_dir = ROOT / BAK_DIR_NAME
    # 注意：这里**不**预先创建备份目录 —— 只有真的要写第一个备份时才建，
    # 保证"参数全错"时零副作用（连目录都不该出现）。

    print(f"项目根：{ROOT}")
    print(f"备份目录：{bak_dir}")
    print(f"时间戳：{stamp}{'（--list 预览，不复制）' if list_only else ''}")
    print("-" * 60)

    ok = 0
    bad = 0
    made: list[tuple[Path, Path]] = []
    for arg in files:
        src, why = _resolve(arg)
        if src is None:
            print(f"  ✗ 跳过 {arg}：{why}")
            bad += 1
            continue
        target = _unique_target(bak_dir, src.name, stamp)
        if list_only:
            print(f"  · 将备份 {src.name} → {target.name}")
            ok += 1
            continue
        if not bak_dir.is_dir():  # 懒创建：只有真的要写备份时才建目录
            try:
                bak_dir.mkdir(parents=True, exist_ok=True)
            except OSError as exc:
                print(f"  ✗ 无法创建备份目录 {bak_dir}：{exc}")
                bad += 1
                continue
        try:
            shutil.copy2(src, target)
        except OSError as exc:
            print(f"  ✗ 复制失败 {src.name}：{exc}")
            bad += 1
            continue
        print(f"  ✓ {src.name} → {target}")
        made.append((src, target))
        ok += 1

    print("-" * 60)
    print(f"成功 {ok} 个｜失败 {bad} 个")
    if made and not list_only:
        print("回退：把上面任一备份文件复制回它的原文件名即可，例如：")
        src, target = made[0]
        print(f'  copy "{target}" "{src}"')
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
