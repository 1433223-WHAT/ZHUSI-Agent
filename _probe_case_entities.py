# -*- coding: utf-8 -*-
"""探查：知识库案例节点结构 + images 目录资产清单（案例实体化前置）。"""
import sys, io, json
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, r"E:\AI\项目设计\筑智AI_ArchAI\ArchAI_Builder")

from local_search import _load_index

meta = _load_index()["metadata"]
print("=== 案例(case_strategy)节点结构 ===")
seen = set()
for m in meta:
    if m.get("type") == "case_strategy":
        key = m.get("case")
        if key in seen:
            continue
        seen.add(key)
        print(json.dumps({k: m.get(k) for k in ("case", "strategy", "category", "architect", "built_year", "source")}, ensure_ascii=False)[:200])
print("\n案例数:", len(seen), "| 案例名:", sorted(seen))

print("\n=== images 目录资产清单 ===")
img_root = Path(r"E:\AI\项目设计\筑智AI_ArchAI\ArchAI_Builder\images")
for d in sorted(img_root.iterdir()):
    if d.is_dir():
        files = sorted(f.name for f in d.iterdir() if f.is_file())
        print(f"{d.name}: {files}")
