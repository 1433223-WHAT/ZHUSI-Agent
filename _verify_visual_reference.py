# -*- coding: utf-8 -*-
"""Visual Context Layer 单元验证：指代解析 + 视觉摘要。"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, r"E:\AI\项目设计\筑智AI_ArchAI\ArchAI_Builder")
from architect_chat import _build_visual_reference

results = []


def check(name, ok, detail=""):
    results.append((name, ok))
    print(("PASS" if ok else "FAIL"), "-", name, detail)


imgs = [
    {"kind": "image", "filename": "a.png", "visible_facts": ["矩形体量", "南向开窗"], "inferences": [{"content": "若此处为入口需验证"}], "unknowns": ["缺比例尺"]},
    {"kind": "image", "filename": "b.png", "visible_facts": ["两个房间", "门"], "inferences": [], "unknowns": ["无标高"]},
]

# 无图 → 空
check("无图返回空", _build_visual_reference([], "看到图了吗") == "", "")
# 有图 + "看到这两张图了吗" → 两张都注入
r = _build_visual_reference(imgs, "看到这两张图了吗")
check("两张→全部注入", "图片1" in r and "图片2" in r, "")
check("摘要含事实/推测/未知", "可见事实" in r and "推测" in r and "未知" in r, "")
# 第一张
r1 = _build_visual_reference(imgs, "第一张是什么")
check("第一张→只用图1", "图片1" in r1 and "图片2" not in r1, "")
check("第一张含其事实", "矩形体量" in r1, "")
# 第二张
r2 = _build_visual_reference(imgs, "第二张呢")
check("第二张→只用图2", "两个房间" in r2 and "矩形体量" not in r2, "")
# 现在呢（承接，默认全部）
r3 = _build_visual_reference(imgs, "现在呢")
check("现在呢→全部", "图片1" in r3 and "图片2" in r3, "")

fails = [r for r in results if not r[1]]
print("=" * 40, f"{len(results)} 项，失败 {len(fails)}")
raise SystemExit(1 if fails else 0)
