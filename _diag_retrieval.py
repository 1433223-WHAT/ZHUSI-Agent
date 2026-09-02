# -*- coding: utf-8 -*-
"""检索能力诊断：不同问法下 local_retrieve 是否召回"案例实体"本体。"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, r"E:\AI\项目设计\筑智AI_ArchAI\ArchAI_Builder")
from local_search import local_retrieve

QUERIES = [
    "光之教堂",
    "光之教堂图片",
    "光之教堂平面图",
    "光之教堂怎么采光",
    "光之教堂为什么用狭缝采光",
    "社区图书馆案例",
    "给我看看类似案例",
    "教学楼案例",
    "金贝尔艺术博物馆",
    "住吉的长屋",
]

for q in QUERIES:
    r = local_retrieve(q, top_k=3)
    cases = [f"{i['name']}({round(i['score'],3)})" for i in r["cases"]]
    theory = [f"{i['name']}({round(i['score'],3)})" for i in r["theory"]]
    methods = [f"{i['name']}({round(i['score'],3)})" for i in r["methods"]]
    print(f"\n查询: {q}")
    print(f"  cases:   {cases}")
    print(f"  theory:  {theory}")
    print(f"  methods: {methods}")
