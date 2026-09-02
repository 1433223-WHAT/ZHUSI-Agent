# -*- coding: utf-8 -*-
"""批 1 验收：问题型检索测试（设计问题→召回对应案例）+ 案例名直查 + 实体化。"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, r"E:\AI\项目设计\筑智AI_ArchAI\ArchAI_Builder")
from local_search import local_retrieve
from case_entities import find_case_entity

results = []


def check(name, ok, detail=""):
    results.append((name, ok))
    print(("PASS" if ok else "FAIL"), "-", name, detail)


# ① 问题型检索：设计问题 → 应召回对应案例（Top-3 cases 内）
PROBLEM_QUERIES = [
    ("中国中学，用地紧张，想要院落和屋顶活动空间", "北京市第四中学房山校区"),
    ("想要安静、面向海的阅读空间", "三联海边图书馆"),
    ("幼儿园想让孩子们自由探索，身体尺度怎么处理", "Kids_Republic"),
]
for q, want in PROBLEM_QUERIES:
    r = local_retrieve(q, top_k=3)
    names = [i["name"] for i in r["cases"]]
    check(f"问题型 [{want}]", want in names, f"{q} -> {names}")

# ② 案例名直查（含别名）
NAME_QUERIES = [
    ("北京四中房山校区怎么样", "北京市第四中学房山校区"),
    ("孤独图书馆", "三联海边图书馆"),
    ("儿童王国案例", "Kids_Republic"),
]
for q, want in NAME_QUERIES:
    e = find_case_entity(q)
    check(f"实体 [{want}]", bool(e) and e["name"] == want, f"{q} -> {e and e['name']}")

# ③ 新案例无图 → 诚实（assets 空，不编造）
e1 = find_case_entity("北京四中")
check("新案例无图(资产0)", e1 and len(e1["assets"]) == 0, f"{e1 and len(e1['assets'])}张")

fails = [r for r in results if not r[1]]
print("=" * 40, f"{len(results)} 项，失败 {len(fails)}")
raise SystemExit(1 if fails else 0)
