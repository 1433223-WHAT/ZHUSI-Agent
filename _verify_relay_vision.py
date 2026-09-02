# -*- coding: utf-8 -*-
"""测试中转站视觉模型：relay 优先调用 + 结果结构。"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, r"E:\AI\项目设计\筑智AI_ArchAI\ArchAI_Builder")
from image_analyzer import _load_relay_config, analyze_architecture_image

cfg = _load_relay_config()
print("relay 配置: base=", cfg.get("base"), "| key 配置=", bool(cfg.get("key")), "| model=", cfg.get("model"))

data = open(r"E:\AI\项目设计\筑智AI_ArchAI\ArchAI_Builder\images\Church_of_the_Light\plan.jpg", "rb").read()
r = analyze_architecture_image("plan.jpg", data, "这是建筑平面图，请分析")
print("status:", r.get("status"))
if r.get("status") == "analyzed":
    print("image_type:", r.get("image_type"))
    print("visible_facts:", len(r.get("visible_facts") or []), "条")
    print("dimension_annotations:", (r.get("dimension_annotations") or [])[:3])
    print("numeric:", len((r.get("numeric_verification") or {}).get("annotations") or []), "条")
    print("facts 样例:", (r.get("visible_facts") or ["-"])[0][:60])
else:
    print("error:", r.get("error"))
    raise SystemExit(1)
