# -*- coding: utf-8 -*-
"""V2 案例迁移权控制验证：Router 识别 / A-B 分阶段 / 防越权 / 框架归属。"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, r"E:\AI\项目设计\筑智AI_ArchAI\ArchAI_Builder")

from intent_router import route
from architect_chat import _handle_case_transfer
from conversation_state import empty_state

results = []


def check(name, ok, detail=""):
    results.append((name, ok))
    print(("PASS" if ok else "FAIL"), "-", name, detail)


# ① Router 识别
cls = {"intent": "design_development", "design_stage": "undecided", "info_status": "sufficient",
       "decision_status": "exploring", "needs": ["none"], "reason": ""}
r1 = route("我想参考光之教堂设计教学楼", {}, cls)
check("Router 参考→case_transfer", r1["pre_action"] == "case_transfer", r1["pre_action"])
r2 = route("想借鉴金贝尔的手法做图书馆", {}, cls)
check("Router 借鉴→case_transfer", r2["pre_action"] == "case_transfer", r2["pre_action"])
r3 = route("光之教堂为什么用狭缝采光", {}, cls)
check("Router 了解案例→非transfer", r3["pre_action"] != "case_transfer", r3["pre_action"])
r4 = route("光之教堂图片", {}, cls)
check("Router 看图→case_image", r4["pre_action"] == "case_image_query", r4["pre_action"])

# ② A 阶段（首轮）：只讲案例里有什么，防越权
h1 = _handle_case_transfer("我想参考光之教堂设计教学楼", empty_state(), 1)
rep = h1["reply"]
check("A 不定义唯一核心", "核心" not in rep or "唯一核心" not in rep, rep[:40])
check("A 不判局部/整体", "局部" not in rep and "而不是" not in rep, "")
check("A 不给完整迁移路线", "列出" not in rep and "画剖面" not in rep and "3 个空间" not in rep, "")
check("A 不造二元框架", "还是偏" not in rep and "还是明亮" not in rep, "")
check("A 开放式问兴趣", ("被哪一点吸引" in rep or "从几个角度阅读" in rep), rep[:60])
check("A 案例资产卡", h1["case_assets"] and len(h1["case_assets"][0]["assets"]) == 8, f"{h1['case_assets'][0]['assets'] and len(h1['case_assets'][0]['assets'])} 张")
check("A transfer_focus=observe", h1["state"]["transfer_focus"]["stage"] == "observe", str(h1["state"]["transfer_focus"]))
trail = h1["state"].get("framework_trail", [])
check("A 框架归属 ai_suggestion", any(t["origin"] == "ai_suggestion" for t in trail), str([t["origin"] for t in trail]))

# ③ B 阶段（学生表达兴趣）：确认兴趣，仍不进入迁移判断
st2 = {"transfer_focus": {"case": "光之教堂", "stage": "observe", "turn": 1}}
h2 = _handle_case_transfer("我喜欢它那个光", st2, 2)
rep2 = h2["reply"]
check("B 确认兴趣", "被「光之教堂」的光吸引" in rep2, rep2[:50])
check("B 不给迁移路线", all(w not in rep2 for w in ["画剖面", "局部", "而不是", "楼梯", "走廊", "光缝怎么做"]), "")
check("B 强调不急着迁移", "不急着判断" in rep2, "")
check("B stage=interest", h2["state"]["transfer_focus"]["stage"] == "interest", str(h2["state"]["transfer_focus"]))

# ④ 防升级：学生弱确认不升级 student_decisions
st3 = {"transfer_focus": {"case": "光之教堂", "stage": "observe", "turn": 1}}
h3 = _handle_case_transfer("嗯可以", st3, 3)
check("弱确认不升级决定", len(h3["state"].get("student_decisions", [])) == 0, str(h3["state"].get("student_decisions")))

fails = [r for r in results if not r[1]]
print("=" * 40, f"{len(results)} 项，失败 {len(fails)}")
raise SystemExit(1 if fails else 0)
