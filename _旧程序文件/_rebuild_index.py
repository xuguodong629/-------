# -*- coding: utf-8 -*-
"""重建知识库索引（总索引 + 各目录索引）。"""
import sys

sys.stdout.reconfigure(encoding="utf-8")
import core

cfg = core.load_config()
print("知识库：", cfg.get("knowledge_base"))
result = core.build_index(cfg)
print("状态：", "OK" if result["ok"] else "FAIL")
for line in result["report"]:
    print(" ", line)
print("目录索引数：", len(result["dirs"]))