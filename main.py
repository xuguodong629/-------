# -*- coding: utf-8 -*-
"""
main.py —— 历史知识库 V1.0 · 程序入口（配置驱动）

配置驱动设计：
  * 首次运行生成**零预设** config.json（知识库留空，由①页自己选；类型映射由②页扫描该库生成）；
  * 程序只在选定的知识库目录上「识别 → 指向 → 写入」，不接管任何目录规划。

打包成 exe 之后：
  * config.json 与 exe 放在同一目录（见 core.BASE_DIR），换机器时连配置一起拷走即可；
  * 自检：`<程序>.exe --selftest`
    无界面启动一次，把结果写到 exe 同级的 _自检报告.txt，退出码 0=通过。
"""
import sys
from pathlib import Path

import tkinter as tk

import core
import gui


def _pin_utf8_stdio() -> None:
    """把标准输出钉成 UTF-8。

    中文只有在输出编码和读取端一致时才是可读的：控制台窗口里 Windows 用
    宽字符 API 渲染，管道/重定向/集成终端里读的却是字节。不钉死编码时，
    Python 会按系统 ANSI 代码页（简体中文机器上是 GBK）输出，于是日志和
    终端里就是乱码。窗口模式（sys.stdout 为 None）下直接跳过。
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass


_pin_utf8_stdio()


def run_selftest() -> int:
    """无界面自检：构建一次窗口后立即退出，结果写入 exe 同级的 _自检报告.txt。"""
    ok = True
    lines = []
    core.install_excepthook()
    try:
        lines.append(f"冻结运行(frozen)：{getattr(sys, 'frozen', False)}")
        lines.append(f"可执行文件：{sys.executable}")
        lines.append(f"程序目录 BASE_DIR：{core.BASE_DIR}")
        lines.append(f"配置文件：{core.CONFIG_FILE}（存在={core.CONFIG_FILE.exists()}）")

        root = tk.Tk()
        gui.main(root)
        root.update_idletasks()
        lines.append(f"GUI 构建 OK：{root.title()}")

        cfg = core.load_config()
        core.log_startup(cfg)
        routes = core.test_routes(cfg)
        bad = [t for t in routes if not t["ok"]]
        lines.append(f"知识库：{cfg.get('knowledge_base') or '（未设置）'}")
        kb = core.resolve_kb(cfg)
        if kb is None:
            lines.append("知识库状态：路径不存在（可在界面「① 知识库设置」中重新选择）")
        else:
            lines.append(f"知识库状态：OK，扫描到 {len(core.scan_kb(kb))} 个目录")
            lines.append(f"路由检查：{len(routes) - len(bad)} 项 OK，{len(bad)} 项缺失")
        root.destroy()
    except Exception as exc:  # 自检本身不能把异常抛出去
        ok = False
        lines.append(f"自检失败：{type(exc).__name__}: {exc}")

    lines.append(f"结果：{'PASS' if ok else 'FAIL'}")
    core.log_event("INFO" if ok else "ERROR", "启动", "自检完成",
                   result=("PASS" if ok else "FAIL"),
                   kb=Path(str(core.load_config().get("knowledge_base") or "")).name)
    text = "\n".join(lines)
    print(text)  # 窗口模式(sys.stdout=None)下 print 静默返回，不影响
    try:
        (core.BASE_DIR / "_自检报告.txt").write_text(text + "\n", encoding="utf-8")
    except Exception:
        pass
    return 0 if ok else 1


def main():
    core.install_excepthook()                      # 未捕获异常写进运行日志
    core.log_startup(core.load_config())           # 记录启动现场（当前库/路由/模板/目录缺失）
    root = tk.Tk()
    gui.main(root)
    root.mainloop()


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(run_selftest())
    main()
