# -*- coding: utf-8 -*-
"""
migrate_format.py —— 把知识库笔记从「编号型」格式迁移为「emoji 型」模板格式。

规则：
  * 只有存在 emoji 型「目录同名模板」的目录才迁移（02~10、12~14）；
  * 01 时间线 / 00 首页 / 11 专题研究 无 emoji 模板，保持编号型不动；
  * 已是 emoji 型（frontmatter 含 title: 字段）的文件跳过；
  * 迁移前先备份到 _备份/笔记/<相对路径>（统一备份目录，只留最新一份）；
  * AI 严格按模板格式输出，保留全部史实、人物、事件、双链 [[]]。

用法：
  python migrate_format.py --pilot           # 试点：02 人物图谱 前 5 个文件
  python migrate_format.py --all             # 全量
  python migrate_format.py --dir "02 人物图谱"  # 单目录
"""
from __future__ import annotations

import argparse
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import core
from ai_client import AIClient, AIError

HERE = core.app_dir()  # 源码运行=项目目录；打包成 exe 后=exe 所在目录
LOG_FILE = HERE / "格式迁移日志.txt"

KB = Path(r"G:\个人文件\知识库-历史\00-Inbox\历史\19民国")
TPL_DIR = KB / "Templates（模板）"
SKIP_DIR_PARTS = ("Templates", "模板", "assets", "附件", "资产")

# emoji 型模板的标志章节
EMOJI_MARKERS = ("🪪", "📌", "📜", "🏛️", "⚔️", "🔗", "📚", "📝", "📅", "👤",
                 "🏷️", "👥", "🎯", "📋", "💀", "🌊", "📇", "📄", "✅", "⚠️",
                 "🗺️", "📈", "🤝", "🌍", "📎", "🔍", "💰", "📖", "🧭", "📊")

# 不参与迁移的目录（首页是 dashboard 模板，essay 是长文）
EXCLUDE_DIRS = ("00 首页", "11 专题研究")


def tpl_for_dir(dirname: str) -> str | None:
    """目录名 → 模板文本（目录同名模板，emoji 或编号型均可；无则 None）。"""
    norm = re.sub(r"^\d+\s*", "", dirname)
    norm = norm.replace(" ⭐", "").replace("（中文）", "").strip()
    p = TPL_DIR / f"{norm}.md"
    if p.is_file():
        return p.read_text(encoding="utf-8")
    return None


def already_matches(text: str, tpl: str) -> bool:
    """文件是否已符合模板：frontmatter 含标志字段 且 正文含模板首个小节。"""
    t_fm, t_body = core.split_frontmatter(tpl)
    f_fm, f_body = core.split_frontmatter(text)
    if not t_fm or not f_fm:
        return False
    key_fields = {k for k in t_fm if k != "标签"}
    if not key_fields.issubset(set(f_fm.keys())):
        return False
    # 正文：模板第一个 h2 小节的 norm 需出现在文件正文
    t_sections = core.parse_sections(t_body)
    if t_sections:
        first_norm = next(iter(t_sections))
        f_sections = core.parse_sections(f_body or "")
        return first_norm in f_sections
    return True


def is_emoji_style(text: str) -> bool:
    """判断文件是否已是 emoji 型（frontmatter 含 title: 且正文有 emoji 章节）。"""
    fields, _ = core.split_frontmatter(text)
    if fields is not None and "title" in fields:
        return True
    return any(m in text for m in EMOJI_MARKERS)


def strip_fences(text: str) -> str:
    """去掉可能的 ```markdown / ``` 围栏。"""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\s*\n?", "", text)
        text = re.sub(r"\n?```\s*$", "", text)
    return text.strip() + "\n"


def build_prompt(tpl: str, current: str, title: str) -> str:
    return (
        "你是历史知识库的格式迁移助手。请把下面这条已有笔记的内容，"
        "严格按给定模板的格式重新组织输出。\n\n"
        "【目标模板格式（必须严格遵守其 frontmatter 字段与章节结构）】\n"
        f"{tpl}\n\n"
        f"【已有笔记内容（标题：{title}）】\n"
        f"{current}\n\n"
        "【要求】\n"
        "1. 严格按模板的 frontmatter 字段和章节结构输出，逐字遵循模板格式；\n"
        "2. 把已有内容中的史实要点、人物、事件、时间、地点、双链 [[]] 全部保留，"
        "压缩组织到模板对应小节，不得遗漏关键事实；\n"
        "3. 模板中的占位符（如 {{人物姓名}}、{{出生年}}）用已有内容里的真实值替换；"
        "没有对应信息的留空或用 - 占位；\n"
        "4. 只输出最终的文件内容（从 --- 开始到结尾），不要任何解释、不要 ``` 围栏。\n"
    )


def migrate_one(client: AIClient, path: Path, root: Path) -> dict:
    rel = str(path.relative_to(root))
    raw = path.read_text(encoding="utf-8")
    text = raw.strip()
    if not text:
        return {"rel": rel, "status": "SKIP", "detail": "空文件"}
    if is_emoji_style(text):
        return {"rel": rel, "status": "SKIP", "detail": "已是 emoji 型"}

    dirname = path.parent.name
    if dirname in EXCLUDE_DIRS:
        return {"rel": rel, "status": "SKIP", "detail": "目录不参与迁移"}
    tpl = tpl_for_dir(dirname)
    if tpl is None:
        return {"rel": rel, "status": "SKIP", "detail": "无模板"}

    # 编号型模板：文件 frontmatter 已含模板标志字段 → 跳过
    if already_matches(text, tpl):
        return {"rel": rel, "status": "SKIP", "detail": "已匹配模板"}

    prompt = build_prompt(tpl, text, path.stem)
    for attempt in range(3):
        try:
            out = client.chat([{"role": "user", "content": prompt}], max_tokens=4000)
            new_text = strip_fences(out)
            # 校验：以 frontmatter 开头
            if not new_text.startswith("---"):
                raise AIError("输出未以 frontmatter 开头")
            break
        except AIError as e:
            if attempt == 2:
                return {"rel": rel, "status": "ERR", "detail": f"{type(e).__name__}: {str(e)[:120]}"}
            time.sleep(2 + attempt * 3)
    else:
        return {"rel": rel, "status": "ERR", "detail": "未知错误"}

    if new_text == text:
        return {"rel": rel, "status": "SKIP", "detail": "内容未变化"}

    # 备份 + 写回（统一备份目录，同名只留最新一份）
    core.backup_note(path, KB)
    path.write_text(new_text, encoding="utf-8")
    return {"rel": rel, "status": "OK", "detail": f"迁移 {len(new_text)} 字符"}


def log_line(msg: str) -> None:
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(msg + "\n")


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    ap = argparse.ArgumentParser()
    ap.add_argument("--pilot", action="store_true", help="试点：02 人物图谱 前 5 个")
    ap.add_argument("--all", action="store_true", help="全量迁移")
    ap.add_argument("--dir", default="", help="只迁移指定目录")
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()

    cfg = core.load_config()
    ai = cfg.get("ai", {})
    client = AIClient(ai.get("base_url", ""), ai.get("api_key", ""),
                      ai.get("model", ""), float(ai.get("temperature", 0.3)))

    # 收集文件
    all_files = []
    for d in sorted(KB.iterdir()):
        if not d.is_dir():
            continue
        if any(k.lower() in d.name.lower() for k in SKIP_DIR_PARTS):
            continue
        all_files.extend(sorted(d.glob("*.md")))

    if args.pilot:
        person_dir = KB / "02 人物图谱"
        work = sorted(person_dir.glob("*.md"))[:5]
    elif args.dir:
        work = sorted((KB / args.dir).glob("*.md"))
    else:
        work = [f for f in all_files if f.stem != "索引"]

    # 过滤掉无 emoji 模板目录和无索引
    work = [f for f in work if f.stem != "索引"]

    print(f"待迁移文件：{len(work)} 条（仅 emoji 模板目录内，已是 emoji 型/无模板的会跳过）", flush=True)

    t0 = time.time()
    ok_n = skip_n = err_n = 0
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(migrate_one, client, p, KB): p for p in work}
        done = 0
        for fut in as_completed(futs):
            p = futs[fut]
            done += 1
            try:
                r = fut.result()
            except Exception as e:  # noqa: BLE001
                r = {"rel": str(p.relative_to(KB)), "status": "ERR",
                     "detail": f"{type(e).__name__}: {e}"}
            if r["status"] == "OK":
                ok_n += 1
            elif r["status"] == "SKIP":
                skip_n += 1
            else:
                err_n += 1
            msg = f"[{r['status']}] {r['rel']} — {r['detail']}"
            log_line(msg)
            if done % 5 == 0 or r["status"] in ("ERR",):
                print(f"  {done}/{len(work)} {msg}", flush=True)

    dt = time.time() - t0
    summary = f"==== 完成：共{len(work)}条，迁移{ok_n}，跳过{skip_n}，错误{err_n}，用时{dt:.0f}s ===="
    print(summary)
    log_line(summary)
    return 0 if err_n == 0 else 2


if __name__ == "__main__":
    sys.exit(main())