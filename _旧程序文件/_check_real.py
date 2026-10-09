# -*- coding: utf-8 -*-
"""只读校验：用默认配置对真实知识库做扫描与路由测试（不写任何文件）。"""
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import core

cfg = core.load_config()
kb = core.resolve_kb(cfg)
if kb is None:
    print("知识库未设置/路径不存在")
    sys.exit(1)
print("知识库:", cfg["knowledge_base"])
rows = core.scan_kb(kb)
print("扫描到", len(rows), "个目录：")
for r in rows:
    print(f"  {r['name']}  [{r['role']}]  md={r['md_count']}")
print("--- 测试目录（默认映射 vs 实际目录）---")
for t in core.test_routes(cfg):
    print(f"  {'OK  ' if t['ok'] else 'MISS'} {t['type']:>5} -> {t['target']}")
print("--- 模板可解析性 ---")
for typ in ("人物", "派系", "时间线", "事件", "战役", "史料"):
    text, note = core.load_template_text(cfg, typ)
    secs = core.parse_sections(text)
    print(f"  {typ}: 模板='{note}' 小节数={len(secs)}")
print("校验完成（全程只读）")