# -*- coding: utf-8 -*-
"""
test_gui.py —— 界面逻辑离线自测（不联网、不动真实知识库）

运行：python test_gui.py
覆盖：
  * run_task 的线程安全：worker 只入队、**回调一定在主线程**、异常也能带回主线程、
    忙碌控件一定恢复、连续多个任务都不丢；
  * 主线程轮询 _poll_tasks 的正常工作与窗口销毁后不报错。

为什么专门测这个：旧实现是在 worker 线程里调 `root.after`，极端情况下会抛
`main thread is not in main loop`，一旦抛错结果就永不回调、界面会一直停在"运行中…"。
"""
from __future__ import annotations

import sys
import threading
import tkinter as tk

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import gui

# GUI 自测也写运行日志：指到沙盒临时目录，避免污染真实 _日志\
import os as _os, tempfile as _tempfile
_os.environ.setdefault("KB_LOG_DIR", _tempfile.mkdtemp(prefix="kb_testgui_log_"))

RESULTS: list[str] = []
FAILS = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global FAILS
    mark = "PASS" if ok else "FAIL"
    if not ok:
        FAILS += 1
    line = f" [{mark}] {name}" + (f"  — {detail}" if detail else "")
    RESULTS.append(line)
    print(line)


def main() -> int:
    root = tk.Tk()
    root.withdraw()
    app = gui.App(root)
    root.update_idletasks()

    # ---- 1. 成功任务：结果与主线程 ----
    seen: dict = {}

    def cb_ok(r):
        seen["result"] = r
        seen["in_main"] = threading.current_thread() is threading.main_thread()
        seen["busy_after"] = app._busy
        root.after(10, root.quit)

    app.run_task(lambda: 6 * 7, cb_ok, "测试任务", busy=(app.btn_tpl_paste,))
    root.after(8000, root.quit)
    root.mainloop()
    check("run_task：结果回到回调", seen.get("result") == 42, str(seen.get("result")))
    check("run_task：回调在**主线程**里执行（线程安全）", seen.get("in_main") is True)
    check("run_task：结束后忙碌标志复位", seen.get("busy_after") is False)
    check("run_task：忙碌控件恢复可用",
          str(app.btn_tpl_paste.cget("state")) == "normal", str(app.btn_tpl_paste.cget("state")))

    # ---- 2. 抛异常的任务：异常被带回主线程，不炸主循环 ----
    err: dict = {}

    def cb_err(r):
        err["r"] = r
        err["in_main"] = threading.current_thread() is threading.main_thread()
        root.after(10, root.quit)

    def boom():
        raise ValueError("模拟后台异常")
    app.run_task(boom, cb_err, "会抛错的任务")
    root.after(8000, root.quit)
    root.mainloop()
    check("run_task：后台异常以 ERROR 元组回到回调",
          isinstance(err.get("r"), tuple) and err["r"][0] == "ERROR"
          and "模拟后台异常" in str(err["r"][1]), str(err.get("r"))[:80])
    check("run_task：出错时回调也在主线程", err.get("in_main") is True)
    check("run_task：出错后忙碌标志也复位", app._busy is False)

    # ---- 3. 连续多个任务都不丢 ----
    got: list = []

    def make_cb(i):
        def cb(r):
            got.append((i, r))
            if len(got) >= 5:
                root.after(10, root.quit)
        return cb

    for i in range(5):
        app.run_task(lambda i=i: i * 100, make_cb(i), f"批量任务{i}")
    root.after(8000, root.quit)
    root.mainloop()
    check("run_task：连续 5 个任务全部回调、结果正确",
          sorted(got) == [(i, i * 100) for i in range(5)], str(sorted(got)))

    # ---- 4. 轮询器：队列空时也不报错，且会继续排下一轮 ----
    app._poll_tasks()
    check("_poll_tasks：队列为空时安静返回、不抛异常", True)

    root.destroy()
    print(f"\n结果：{len(RESULTS) - FAILS}/{len(RESULTS)} 通过，{FAILS} 失败")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
