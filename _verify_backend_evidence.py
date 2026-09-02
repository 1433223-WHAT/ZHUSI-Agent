# -*- coding: utf-8 -*-
"""后端单元验证：A+ 分层 / 来源分级 / images / evidence_id（不依赖 HTTP 服务）。"""
import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, r"E:\AI\项目设计\筑智AI_ArchAI\ArchAI_Builder")

from architect_chat import (_detect_mentioned, _detect_unsupported_claims,
                            _knowledge_items, _knowledge_annotations)

results = []


def check(name, ok, detail=""):
    results.append((name, ok))
    print(("PASS" if ok else "FAIL"), "-", name, detail)


# 1) _knowledge_items：status 分级 / evidence_id / images
raw = {
    "cases": [{"name": "巴塞罗那德国馆", "strategy": "底层架空", "content": "…", "score": 0.9, "source": "https://x.com/a", "architect": "Mies"}],
    "theory": [{"name": "材料感知理论", "content": "…", "score": 0.7, "source": ""}],
    "methods": [{"name": "空间嵌套", "content": "…", "score": 0.6}],
}
items = _knowledge_items(raw)
by_name = {i["name"]: i for i in items}
check("status 有源→has_source", by_name["巴塞罗那德国馆"]["status"] == "has_source", by_name["巴塞罗那德国馆"]["status"])
check("status 无源→in_kb", by_name["材料感知理论"]["status"] == "in_kb", by_name["材料感知理论"]["status"])
check("evidence_id 格式", by_name["巴塞罗那德国馆"]["evidence_id"] == "case:巴塞罗那德国馆", by_name["巴塞罗那德国馆"]["evidence_id"])
imgs = by_name["巴塞罗那德国馆"]["images"]
check("images 真实文件(plan/space_01 存在, 无 section/interior)", imgs == ["plan.jpg", "space_01.jpg", "space_02.jpg", "space_03.jpg"], str(imgs))

# 2) _knowledge_annotations：透传 evidence_id / images / verification_status
ann = _knowledge_annotations(items, "测试", 1)
a0 = ann[0]
check("注解透传 evidence_id", a0["evidence_id"] == "case:巴塞罗那德国馆", a0["evidence_id"])
check("注解透传 images", a0["images"] == imgs, str(a0["images"]))
check("注解透传 status", a0["verification_status"] in ("has_source", "in_kb"), a0["verification_status"])
check("注解不含 verified_source", all(a["verification_status"] != "verified_source" for a in ann), "无 verified_source")

# 3) _detect_mentioned：提到→mentioned，未提→rest
reply1 = "巴塞罗那德国馆的底层架空让空间流动"
men, rest = _detect_mentioned(reply1, items)
check("mentioned 命中 name", any(i["name"] == "巴塞罗那德国馆" for i in men), [i["name"] for i in men])
check("rest 含未提条目", any(i["name"] == "材料感知理论" for i in rest), [i["name"] for i in rest])
men2, _ = _detect_mentioned("底层架空让地面层完全开放", items)
check("mentioned 命中 strategy 短语", any(i["name"] == "巴塞罗那德国馆" for i in men2), [i["name"] for i in men2])

# 4) _detect_unsupported_claims：库中存在但未命中 + 外部参考
knowledge_subset = [items[1]]  # 只带材料感知理论，假装巴塞罗那未被检索
reply2 = "金贝尔艺术博物馆的拱顶节奏值得参考，密斯·凡·德·罗也有类似思考，还有巴塞罗那德国馆。"
claims = _detect_unsupported_claims(reply2, knowledge_subset)
names = {c["name"]: c["type"] for c in claims}
check("unsupported 检出 金贝尔(type=case)", names.get("金贝尔艺术博物馆") == "case", str(names))
check("unsupported 检出 巴塞罗那(库中有未命中)", names.get("巴塞罗那德国馆") == "case", str(names))
check("unsupported 检出 密斯(外部 theory)", names.get("密斯·凡·德·罗") == "theory", str(names))
# 已检索到的不算 unsupported
claims2 = _detect_unsupported_claims(reply2, items)
check("已检索条目不算 unsupported", "巴塞罗那德国馆" not in {c["name"] for c in claims2}, str([c["name"] for c in claims2]))

fails = [r for r in results if not r[1]]
print("=" * 40, f"{len(results)} 项，失败 {len(fails)}")
raise SystemExit(1 if fails else 0)
