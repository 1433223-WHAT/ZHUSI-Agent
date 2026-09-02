# -*- coding: utf-8 -*-
"""验证新案例检索与实体化。"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, r"E:\AI\项目设计\筑智AI_ArchAI\ArchAI_Builder")
from local_search import local_retrieve
from case_entities import find_case_entity

print("=== 检索新案例 ===")
for q in ["幼儿园 环形 活动场地", "社区图书馆 中庭 公共", "教学楼 中庭 学生交流", "书架 台阶 一体化"]:
    r = local_retrieve(q, top_k=3)
    names = [i["name"] for i in r["cases"]]
    print(f"{q}: {names}")

print()
print("=== 实体化 ===")
for q in ["藤幼儿园", "天津滨海图书馆", "奥雷斯塔高中", "社区图书馆有什么案例"]:
    e = find_case_entity(q)
    if e:
        print(f"{q}: {e['name']} 建筑师={e['architect'][:20]} 资产={len(e['assets'])}张")
    else:
        print(f"{q}: None")
