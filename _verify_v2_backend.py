# -*- coding: utf-8 -*-
"""V2 后端单元验证：案例实体 / 资产筛选 / 检索焦点继承 / case_image handler。"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, r"E:\AI\项目设计\筑智AI_ArchAI\ArchAI_Builder")

from case_entities import find_case_entity, get_case_assets, get_case_entity
from architect_chat import _resolve_retrieval_focus, _handle_case_image_query

results = []


def check(name, ok, detail=""):
    results.append((name, ok))
    print(("PASS" if ok else "FAIL"), "-", name, detail)


# 1) 案例实体
e = find_case_entity("光之教堂图片")
check("实体 光之教堂", bool(e) and e["name"] == "光之教堂", str(e and e["name"]))
check("实体 资产 8 张全真实", e and len(e["assets"]) == 8, f"{e and len(e['assets'])} 张")
labels = {a["file"]: (a["label"], a["kind"]) for a in e["assets"]}
check("资产类型 平面图=原始", labels.get("plan.jpg") == ("平面图", "original"), str(labels.get("plan.jpg")))
check("资产类型 plan_analysis=分析", labels.get("plan_analysis.jpg") == ("平面分析图", "analysis"), str(labels.get("plan_analysis.jpg")))
check("资产类型 light_path=分析", labels.get("light_path.jpg") == ("光路径分析图", "analysis"), str(labels.get("light_path.jpg")))
check("资产类型 space_01=照片", labels.get("space_01.jpg") == ("空间照片", "photo"), str(labels.get("space_01.jpg")))

# 2) 别名
e2 = find_case_entity("有没有住吉长屋的图")
check("别名 住吉长屋→住吉的长屋", bool(e2) and e2["name"] == "住吉的长屋", str(e2 and e2["name"]))
e3 = find_case_entity("给我看看金贝尔平面图")
check("别名 金贝尔→金贝尔艺术博物馆", bool(e3) and e3["name"] == "金贝尔艺术博物馆", str(e3 and e3["name"]))

# 3) 资产筛选
p = get_case_assets("光之教堂", "平面")
check("筛选 平面 = 2 张", [a["file"] for a in p] == ["plan.jpg", "plan_analysis.jpg"], str([a["file"] for a in p]))
photo = get_case_assets("光之教堂", "照片")
check("筛选 照片 ≥ 2 张", len(photo) >= 2, str([a["file"] for a in photo]))

# 4) 检索焦点继承
f1 = _resolve_retrieval_focus("光之教堂图片", {})
check("焦点 明确案例=新焦点", f1["case"] == "光之教堂" and not f1["inherited"], str(f1))
state_focus = {"retrieval_focus": {"case": "光之教堂", "asset_kw": "", "intent": "case_image_query"}}
f2 = _resolve_retrieval_focus("有平面的吗", state_focus)
check("焦点 承接'有平面的吗'", f2["case"] == "光之教堂" and f2["inherited"] and f2["asset_kw"] == "平面", str(f2))
f3 = _resolve_retrieval_focus("你从知识库里找", state_focus)
check("焦点 承接'你从知识库里找'", f3["case"] == "光之教堂" and f3["inherited"], str(f3))

# 5) case_image handler
h1 = _handle_case_image_query("光之教堂图片", {}, 1)
check("handler 资产 8 张", h1 and h1["case_assets"] and len(h1["case_assets"][0]["assets"]) == 8, str(h1 and len(h1["case_assets"][0]["assets"])))
check("handler reply 含'8 张'", h1 and "8 张" in h1["reply"], str(h1 and h1["reply"][:60]))
check("handler 不调 LLM", h1 and h1["model_called"] is False, str(h1 and h1["model_status"]))
check("handler focus 记录", h1 and h1["state"]["retrieval_focus"]["intent"] == "case_image_query", str(h1 and h1["state"].get("retrieval_focus")))
check("handler 资产区分分析/原始", h1 and "筑思分析图" in h1["reply"] and "原始图纸" in h1["reply"], "")

h2 = _handle_case_image_query("有平面的吗", state_focus, 2)
check("handler 承接筛平面 2 张", h2 and len(h2["case_assets"][0]["assets"]) == 2, str(h2 and [a["file"] for a in h2["case_assets"][0]["assets"]]))

fails = [r for r in results if not r[1]]
print("=" * 40, f"{len(results)} 项，失败 {len(fails)}")
raise SystemExit(1 if fails else 0)
