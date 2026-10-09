# -*- coding: utf-8 -*-
"""
_build_exe.py —— 把程序打包成单文件 exe（真正干活的脚本）。

为什么要用 Python 而不是直接写批处理：
  * 批处理里有中文时，cmd 按字节偏移逐行读取，一旦文件里有 chcp 或
    代码页与文件编码不一致，解析就会错位（实测会出现 'cho' / 'n.py' 之类的报错）；
  * Python 全程用 Unicode 参数调用 PyInstaller（subprocess 列表形式），
    中文路径/中文 exe 名都不会出问题。

用法：
    py _build_exe.py            正常打包
    py _build_exe.py --clean    先清空 build/ 再打包（全新构建）
"""
from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXE_NAME = "历史知识库"
DIST = HERE / "dist"
BUILD = HERE / "build"

# 子进程（pip / PyInstaller）也强制 UTF-8，中文路径在日志里才不会乱码
CHILD_ENV = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}

try:                                    # 统一 UTF-8 输出（控制台/重定向都不会乱码）
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def step(msg: str) -> None:
    print(f"\n=== {msg} ===", flush=True)


def ensure_pyinstaller() -> None:
    if importlib.util.find_spec("PyInstaller") is not None:
        print("PyInstaller 已安装")
        return
    print("未检测到 PyInstaller，正在安装 ...")
    subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"],
                   check=True, env=CHILD_ENV)


def make_icon() -> None:
    try:
        import _make_icon
    except ModuleNotFoundError:
        print("（_make_icon.py 不存在，跳过图标重建，沿用现有 app.ico）")
        return

    _make_icon.OUT.write_bytes(_make_icon.build_ico())
    print(f"图标已生成：{_make_icon.OUT.name}（{_make_icon.OUT.stat().st_size} 字节）")


def _clean_dist_runtime() -> None:
    """打包前清掉 dist 里的运行期产物（_备份/_词表/词表/自检报告），**绝不删 config.json**。"""
    dist = HERE / "dist"
    if not dist.is_dir():
        return
    for name in ("_备份", "_词表", "_链接词表.json", "_自检报告.txt"):
        p = dist / name
        try:
            if p.is_dir():
                shutil.rmtree(p)
            elif p.is_file():
                p.unlink()
            print(f"[清理] dist/{name}")
        except Exception as exc:
            print(f"[清理] 跳过 dist/{name}：{exc}")


def run_pyinstaller(clean: bool) -> None:
    args = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",                       # 覆盖 dist 里已存在的 exe
        "--onefile",                         # 单文件
        "--windowed",                        # GUI 程序，不弹黑色控制台
        "--name", EXE_NAME,
        "--icon", "app.ico",
        "--add-data", "app.ico;.",           # 运行时窗口图标
        "--version-file", "_version_info.txt",
        "--distpath", str(DIST),
        "--workpath", str(BUILD),
        "--specpath", str(HERE),
        "main.py",
    ]
    if clean:
        args.insert(3, "--clean")
    print(" ".join(args[1:]))
    subprocess.run(args, cwd=HERE, check=True, env=CHILD_ENV)


def copy_config(force: bool = False) -> None:
    """把项目 config.json 复制到 dist。

    **默认不会覆盖 dist 里已有的 config.json** —— 因为那里面存着用户运行时
    选的知识库、类型映射、模板库等选择；打包时覆盖它会让程序"自己换了库"
    （曾经真的发生过）。想强制用项目版覆盖，加 --sync-config。
    """
    src, dst = HERE / "config.json", DIST / "config.json"
    if not src.exists():
        print("警告：项目目录没有 config.json，exe 首次启动会用默认配置")
        return
    if dst.exists() and not force:
        print(f"保留 dist 里已有的 config.json（不动用户选的知识库等设置）：{dst}")
        print("  想用项目 config.json 覆盖它，请加参数 --sync-config")
        return
    shutil.copy2(src, dst)
    print(f"配置已复制：{dst}")


def main() -> int:
    clean = "--clean" in sys.argv
    print("=" * 60)
    print("  历史知识库 · 打包成单文件 exe")
    print("=" * 60)

    step("1/4 检查 PyInstaller")
    ensure_pyinstaller()

    step("2/4 生成图标 app.ico")
    make_icon()

    step("3/4 打包 main.py（首次约 1 分钟）")
    _clean_dist_runtime()
    run_pyinstaller(clean)

    step("4/4 同步 config.json 到 dist（默认保留 dist 里已有的那份）")
    copy_config(force="--sync-config" in sys.argv)

    exe = DIST / f"{EXE_NAME}.exe"
    print("\n" + "=" * 60)
    if exe.exists():
        print(f"  打包完成：{exe}")
        print(f"  体积：{exe.stat().st_size / 1024 / 1024:.2f} MB")
        print("  发布时把整个 dist 文件夹拷走即可（exe 与 config.json 必须同目录）")
        print(f"  自检：\"{exe.name}\" --selftest")
        print("=" * 60)
        return 0
    print("  打包失败：没有找到生成的 exe，请查看上面的报错")
    print("=" * 60)
    return 1


if __name__ == "__main__":
    sys.exit(main())
