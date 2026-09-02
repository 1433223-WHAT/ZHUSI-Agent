# -*- coding: utf-8 -*-
"""clarify 过度诊断：真实 classify + route，检查哪些场景仍误触发澄清模板。"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, r"E:\AI\项目设计\筑智AI_ArchAI\ArchAI_Builder")

from intent_router import classify, route

CASES = [
    ("空间有点平", {}),                                  # 模糊评价 → clarify（期望）
    ("入口太普通了", {}),                                # 模糊评价 → clarify（期望）
    ("门厅有点挤", {}),                                  # 模糊评价 → clarify（期望）
    ("光之教堂为什么用狭缝采光", {}),                     # 知识问题 → 不应 clarify
    ("有没有中庭采光的案例", {}),                         # 案例检索 → 不应 clarify
    ("我想做教学楼", {}),                                 # 新任务 → 不应 clarify
    ("教室朝南怎么样", {}),                               # 具体信息 → 不应 clarify
    ("水吧放在哪比较好", {}),                             # 具体问题 → 不应 clarify
    ("我觉得入口可以有仪式感", {}),                       # 具体想法 → 不应 clarify
    ("评图老师觉得我的立面太平", {}),                     # 老师反馈转述 → 不应 clarify
    ("帮我看看我的平面图", {}),                           # 上传分析 → 不应 clarify
    ("这个设计怎么样", {}),                               # 泛评图 → 可接受 clarify（模糊）或 direct
    ("金贝尔的拱顶怎么做出来的", {}),                     # 案例知识问题 → 不应 clarify
    ("楼梯间的采光不够", {}),                             # 具体问题 → 不应 clarify
]

print(f"{'消息':<28} intent | info | pre_action")
print("-" * 78)
bad = []
for msg, state in CASES:
    cls = classify(msg, state)
    if cls is None:
        print(f"{msg:<28} classify失败(降级) -> direct")
        continue
    r = route(msg, state, cls)
    line = f"{msg:<28} {cls['intent']:<16} {cls['info_status']:<14} {r['pre_action']}"
    print(line)
    # 误触发 clarify 的判定（人工核对，只标出 clarify 的行）
    if r["pre_action"] == "clarify":
        print("   ^ CLARIFY")
