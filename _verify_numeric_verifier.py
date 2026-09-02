# -*- coding: utf-8 -*-
"""Numeric Verifier 单元验证。"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, r"E:\AI\项目设计\筑智AI_ArchAI\ArchAI_Builder")
from numeric_verifier import verify_numeric, display_mm

results = []


def check(name, ok, detail=""):
    results.append((name, ok))
    print(("PASS" if ok else "FAIL"), "-", name, detail)


# ① 用户案例：只识别出 6m×14m（漏首位 2）→ 不能 confirmed，必须待核验
r1 = verify_numeric(["建筑总长度为6m，总宽度为14m"])
s1 = {a["kind"]: a["status"] for a in r1["annotations"]}
check("6m 漏首位→不confirmed", all(st != "confirmed" for st in s1.values()), str(s1))
check("6m 默认待核验(uncertain)", all(st == "uncertain" for st in s1.values()), str(s1))

# ② 尺寸链矛盾：分段 3600+4200+3600+4200+10400=26000 vs 总 6000 → 总 conflicting
r2 = verify_numeric(["分段尺寸：3600、4200、3600、4200、10400", "总长度 6000"])
tot = next(a for a in r2["annotations"] if a["kind"] == "total_length")
check("尺寸链矛盾→总尺寸conflicting", tot["status"] == "conflicting", tot["status"] + " " + tot.get("conflict_note", ""))

# ③ 尺寸链一致：分段和=总 → confirmed
r3 = verify_numeric(["分段：3600、4200、3600、4200、10400", "总长度 26000"])
tot3 = next(a for a in r3["annotations"] if a["kind"] == "total_length")
check("尺寸链一致→confirmed", tot3["status"] == "confirmed", tot3["status"])

# ④ 比例弱校验：横向长条但识别 14m×6m（长<宽）→ 冲突提示
r4 = verify_numeric(["横向长条的体量", "建筑 6m × 14m"])
check("比例矛盾→冲突提示", len(r4["conflicts"]) >= 1, str(r4["conflicts"]))

# ⑤ 无数字 → 空
r5 = verify_numeric(["矩形体量，南向开窗"])
check("无数字→空", r5["annotations"] == [], "")

# ⑥ 显示格式
check("显示 mm→m", display_mm(26000) == "26m", display_mm(26000))

# ⑦ 标注-对象关系误绑定：图里有 6000 和 265000，模型把 6000 绑定成总长 → 绑定可疑
r6 = verify_numeric(
    ["建筑总长度6000，总宽度14000"],
    dimension_annotations=["左侧标注6000", "外侧标注265000", "下方标注14000"],
)
check("绑定验证 6000被质疑", len(r6["bind_suspects"]) >= 1, str(r6["bind_suspects"]))
check("绑定验证 指出更大标注265000", any("265000" in str(b.get("bigger_values")) for b in r6["bind_suspects"]), str(r6["bind_suspects"]))

# ⑧ 无更大标注时绑定不质疑
r7 = verify_numeric(["建筑总长度14000"], dimension_annotations=["外侧标注14000"])
check("绑定验证 无更大值→不质疑", r7["bind_suspects"] == [], str(r7["bind_suspects"]))

# ⑨ 第二张图场景：读到明确总宽 14000 → 不再求和成 28m（撤掉全量求和）
r8 = verify_numeric(["建筑总宽度14000"], dimension_annotations=["外侧标注14000", "顶部标注6000", "顶部标注8000"])
has_explicit = any(a["kind"] == "explicit_total" and a["value_mm"] == 14000 for a in r8["annotations"])
check("explicit 总宽=14000 识别", has_explicit, str([a["text"] for a in r8["annotations"] if a["kind"] == "explicit_total"]))
check("不求和成28m/30m", all("28000" not in a["text"] and "30000" not in a["text"] for a in r8["annotations"]), str([a["text"] for a in r8["annotations"]]))

# ⑩ 无明确总尺寸 → note 提示 + 不求和（宁缺毋错）
r9 = verify_numeric(["图中存在尺寸标注"], dimension_annotations=["顶部标注4500", "顶部标注1500", "左侧标注6000"])
check("无总尺寸→note提示", "未可靠读到明确总尺寸" in r9.get("note", ""), r9.get("note", "")[:50])
check("无总尺寸→不产生求和条目", all(a["kind"] not in ("position_sum", "derived") for a in r9["annotations"]), str([a["kind"] for a in r9["annotations"]]))

# ⑪ 完整尺寸链（模型同链给出）→ derived 校验（非全量求和）
r10 = verify_numeric(["分段尺寸：6000、4000、4000", "总宽度 14000"])
tot10 = next((a for a in r10["annotations"] if a["kind"] == "total_width"), None)
check("尺寸链一致→confirmed", tot10 and tot10["status"] == "confirmed", str(tot10 and tot10["status"]))

fails = [r for r in results if not r[1]]
print("=" * 40, f"{len(results)} 项，失败 {len(fails)}")
raise SystemExit(1 if fails else 0)
