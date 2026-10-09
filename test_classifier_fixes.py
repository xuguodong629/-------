# -*- coding: utf-8 -*-
"""test_classifier_fixes.py —— 类型判定回归断言（19民国 / 两晋 两个真实档案配置，全部只读）。

覆盖本轮修的 5 处误判 + 12 条"不许回归"的既有正确判定 + `_check_spec` 的围栏跳过。
用法：py test_classifier_fixes.py     退出码 0 = 全过。
"""
from __future__ import annotations

import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import core
import _check_spec

KB_MINGUO = Path(r"G:\个人文件\知识库-历史\00-Inbox\历史\19民国")
KB_JIN = Path(r"G:\个人文件\知识库-历史\00-Inbox\历史\06第一帝国时代\06-03两晋")

FAILED: list = []


def cfg_for(kb: Path) -> dict:
    """按该库档案取 routes/footer_types/type_keywords（只读，不写盘）。"""
    c = dict(core.load_config())
    c["knowledge_base"] = str(kb)
    prof = core.get_kb_profile(c, kb) or {}
    for k in ("routes", "footer_types", "type_keywords"):
        if prof.get(k) is not None:
            c[k] = prof[k]
    return c


def expect(cfg: dict, words, want: str, label: str) -> None:
    for w in words:
        got = core.match_type_in_kb(cfg, w)[0]
        ok = (got == want)
        if not ok:
            FAILED.append(f"{label}：{w} → {got or '空'}（期望 {want}）")
        print(f"   [{'PASS' if ok else 'FAIL'}] {label}｜{w} → {got or '空'}"
              f"{'' if ok else '（期望 ' + want + '）'}")


def main() -> int:
    if not KB_MINGUO.is_dir() or not KB_JIN.is_dir():
        print("（跳过：真实知识库不可用）")
        return 0
    c_mg, c_jin = cfg_for(KB_MINGUO), cfg_for(KB_JIN)

    print("=== 本轮修正（19民国）===")
    expect(c_mg, ["赵尚志", "阎锡山", "马占山"], "人物", "修正｜人物")
    expect(c_mg, ["国民党一大"], "事件", "修正｜会议类")
    expect(c_mg, ["黄埔军校校史"], "军队", "修正｜军事史类")

    print("=== 不许回归（19民国）===")
    expect(c_mg, ["建康", "洛阳"], "地区", "不回归｜地名")
    expect(c_mg, ["孙中山"], "人物", "不回归｜姓氏+地名")
    expect(c_mg, ["宋书"], "史料", "不回归｜文献")
    expect(c_mg, ["斯大林", "麦克阿瑟", "博古", "粟裕"], "人物", "不回归/新补｜外来人名")
    expect(c_mg, ["军事委员会", "清廷陆军部", "保定陆军军官学校"], "军队", "新补｜军校机构")

    print("=== 不许回归（两晋）===")
    expect(c_jin, ["建康", "洛阳"], "历史地理", "不回归｜地名")
    expect(c_jin, ["谢安北伐", "桓温北伐"], "战争", "不回归｜战事")
    expect(c_jin, ["八王之乱", "衣冠南渡", "桓玄篡位"], "事件", "不回归｜事件")
    expect(c_jin, ["成汉", "东晋", "北魏", "金"], "政权", "不回归｜国号")
    expect(c_jin, ["岳飞", "耶律阿保机", "司马炎"], "人物", "不回归｜人名")
    expect(c_jin, ["澶渊之盟"], "史料", "不回归｜条约类")

    print("=== _check_spec 围栏跳过 ===")
    fenced = "# 测试\n\n```\n## 示例标题\n### 另一个\n```\n\n## 🧪 真小节\n\n- x\n\n---\n**关联**：[[A]]\n"
    bad = [x for x in _check_spec.check_text(fenced) if "§1-4" in x or "§1-5" in x]
    ok = not bad
    if not ok:
        FAILED.append(f"围栏跳过：仍报 {bad}")
    print(f"   [{'PASS' if ok else 'FAIL'}] 围栏内示例标题不参与标题判定")
    real = "# 测试\n\n```\n## 示例\n```\n\n## 1. 真缺 emoji\n\n- x\n\n---\n**关联**：[[A]]\n"
    hit = [x for x in _check_spec.check_text(real) if "§1-4" in x]
    ok2 = bool(hit)
    if not ok2:
        FAILED.append("围栏跳过：围栏外的真问题被漏报 ✗")
    print(f"   [{'PASS' if ok2 else 'FAIL'}] 围栏外真缺 emoji 仍然报出")

    print()
    if FAILED:
        print(f"结果：{len(FAILED)} 条失败")
        for x in FAILED:
            print("   ✗", x)
        return 1
    print("结果：全部通过 ✓")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
