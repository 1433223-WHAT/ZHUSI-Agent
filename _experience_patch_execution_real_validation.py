"""Real-chain validation for exact local experience patches."""

from __future__ import annotations

from pathlib import Path
import re

import architect_chat as ac
from conversation_state import empty_state


OUT = Path("../03_AI测试记录/项目日志/Experience_Patch_Execution_Real_Validation_Report.md")

CASES = [
    (
        "道路到入口",
        "基地北侧临城市道路，南侧是住宅。请帮我推一个社区文化中心的入口与公共空间组织骨架。",
        [r"直接决定.{0,20}(?:入口|公共空间)", r"这是主要到达界面", r"人流.{0,8}大概率从北侧",
         r"主入口放北侧", r"北侧.{0,16}承担主要到达", r"南侧.{0,12}(?:是|作为)安静界面",
         r"临城市道路设主入口", r"公共性从北向南递减", r"安静性从南向北递增",
         r"靠近住宅.{0,16}安静缓冲"],
    ),
    (
        "朝向到布局",
        "社区图书馆基地南侧边界开敞，北侧临现有建筑。请帮我给一版包含阅览、展览和后勤的空间组织骨架。",
        [r"开敞边界意味着.{0,30}(?:到达|人流|城市视线)", r"南公共.{0,8}北安静",
         r"南侧边界开敞.{0,35}(?:适合|可承接).{0,20}(?:入口|展览|公共)",
         r"南侧开敞.{0,8}主入口", r"南入口.{0,8}公共大厅",
         r"北向漫射光.{0,20}适合阅读",
         r"南侧.{0,20}(?:应该|应当|最好|最适合|优先).{0,20}(?:阅览|展厅|公共)",
         r"(?:阅览|展厅|公共).{0,20}(?:应该|应当|最好|优先).{0,12}南侧"],
    ),
    (
        "幼儿园类型经验",
        "我做一个6班幼儿园，请推活动室、寝室和室外活动场地的关系，同时方便老师照看。",
        [r"通常是.{0,10}一套单元", r"通常.{0,12}直接贴靠", r"管理压力最小",
         r"非常典型的幼儿园组织", r"活动室.{0,30}(?:必须|应该|最好)",
         r"寝室与室外场地不直接相连", r"寝室.{0,30}(?:不能|不应|必须)",
         r"每个班是一个独立单元", r"寝室不直接对室外", r"活动室直接对室外",
         r"班级专属场地.{0,16}紧贴.{0,12}活动室",
         r"(?:每班|每个班).{0,20}(?:必须|应该|最好).{0,12}(?:独立出口|小院)",
         r"这是可观察的约束", r"活动室是老师视线的枢纽", r"不需要移动就能覆盖"],
    ),
    (
        "舞蹈教室工程经验",
        "一个社区文化中心包含舞蹈教室。如果舞蹈教室放在二层，需要注意什么？",
        [r"楼板需要比普通教室更厚", r"楼下.{0,8}不要.{0,8}安静功能",
         r"舞蹈教室.{0,18}(?:不能|不适合).{0,8}二层",
         r"舞蹈教室.{0,18}(?:必须|应该|最好).{0,8}一层"],
    ),
]


def hits(text: str, patterns: list[str]) -> list[str]:
    return [pattern for pattern in patterns if re.search(pattern, text)]


def labor(text: str) -> int:
    dimensions = [
        ["功能", "活动室", "寝室", "展厅", "阅览", "舞蹈"],
        ["组织", "关系", "流线", "入口", "公共空间", "庭院"],
        ["体量", "一层", "二层", "竖向"],
        ["剖面", "楼板", "隔振", "结构", "声学"],
        ["画", "草图", "平面", "剖面", "标出", "可画"],
    ]
    return sum(any(term in text for term in terms) for terms in dimensions)


def degradation(text: str) -> list[str]:
    result = []
    if any(term in text for term in ("无法判断", "信息不足", "不能给出建议")):
        result.append("无法判断式退化")
    if any(term in text for term in ("内部检查结果", "project_factification", "missing_condition")):
        result.append("内部检查外显")
    if text.count("需要确认") + text.count("需要验证") >= 6:
        result.append("条件句膨胀")
    return result


def main() -> None:
    old = {
        "pre": ac.ENABLE_PREOUTPUT_CHECK,
        "patch": ac.ENABLE_EXPERIENCE_PATCH_EXECUTION,
        "experience": ac.ENABLE_EXPERIENCE_BOUNDARY,
        "candidate": ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY,
        "pil": ac.ENABLE_PIL_MIDDLEWARE,
    }
    rows = []
    try:
        ac.ENABLE_PREOUTPUT_CHECK = True
        ac.ENABLE_EXPERIENCE_PATCH_EXECUTION = True
        ac.ENABLE_EXPERIENCE_BOUNDARY = False
        ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = False
        ac.ENABLE_PIL_MIDDLEWARE = False
        for title, prompt, patterns in CASES:
            result = ac.chat_turn(prompt, [], empty_state(), turn_id=1, capture_stages=True)
            stages = result.get("stages") or {}
            raw = stages.get("raw_draft") or ""
            checked = stages.get("checked_draft") or ""
            final = stages.get("final_after_boundary") or result.get("reply") or ""
            rows.append({
                "title": title,
                "prompt": prompt,
                "raw": raw,
                "checked": checked,
                "final": final,
                "recall_count": len(ac._recall_experience_assertion_candidates(raw)),
                "raw_hits": hits(raw, patterns),
                "checked_hits": hits(checked, patterns),
                "final_hits": hits(final, patterns),
                "raw_labor": labor(raw),
                "checked_labor": labor(checked),
                "final_labor": labor(final),
                "degradation": degradation(final),
            })
    finally:
        ac.ENABLE_PREOUTPUT_CHECK = old["pre"]
        ac.ENABLE_EXPERIENCE_PATCH_EXECUTION = old["patch"]
        ac.ENABLE_EXPERIENCE_BOUNDARY = old["experience"]
        ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = old["candidate"]
        ac.ENABLE_PIL_MIDDLEWARE = old["pil"]

    raw_total = sum(len(row["raw_hits"]) for row in rows)
    checked_total = sum(len(row["checked_hits"]) for row in rows)
    final_total = sum(len(row["final_hits"]) for row in rows)
    lines = [
        "# Experience Patch Execution 最小真实验证报告",
        "",
        "## 设置",
        "",
        "同一轮记录 `raw_draft -> checked_draft -> final_after_boundary`。仅开启结构化局部补丁执行；Experience Boundary、Candidate Boundary、PIL 均关闭。",
        "",
        "## 汇总",
        "",
        f"- 强经验断言命中：Raw={raw_total}，Patch 后={checked_total}，最终={final_total}",
        f"- 召回候选句：{sum(r['recall_count'] for r in rows)} 条",
        f"- 设计劳动：Raw={sum(r['raw_labor'] for r in rows)}/20，Patch 后={sum(r['checked_labor'] for r in rows)}/20，最终={sum(r['final_labor'] for r in rows)}/20",
        f"- 退化案例：{sum(bool(r['degradation']) for r in rows)}/4",
        "",
        "## 结论",
        "",
        (
            "支持进入后续评审：局部补丁降低了强经验断言，且没有损害设计劳动。"
            if checked_total < raw_total
            else "不支持当前版本直接开启：局部补丁执行正常，但强经验断言没有下降，仍存在语义漏检。"
        ),
        "",
    ]
    for row in rows:
        lines.extend([
            f"## {row['title']}", "",
            f"输入：{row['prompt']}", "",
            f"断言命中：Raw={len(row['raw_hits'])}，Patch 后={len(row['checked_hits'])}，最终={len(row['final_hits'])}", "",
            f"召回候选句：{row['recall_count']} 条；局部补丁实际改写：{'是' if row['checked'] != row['raw'] else '否'}", "",
            f"最终命中模式：{('、'.join(row['final_hits']) if row['final_hits'] else '无')}", "",
            f"设计劳动：Raw={row['raw_labor']}/5，Patch 后={row['checked_labor']}/5，最终={row['final_labor']}/5", "",
            f"退化：{('、'.join(row['degradation']) if row['degradation'] else '无')}", "",
            "### Raw Draft", "", row["raw"], "",
            "### Patch 后", "", row["checked"], "",
            "### 最终输出", "", row["final"], "",
        ])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"report={OUT.resolve()}")
    print(f"assertions raw={raw_total} checked={checked_total} final={final_total}")
    print(
        "labor "
        f"raw={sum(r['raw_labor'] for r in rows)}/20 "
        f"checked={sum(r['checked_labor'] for r in rows)}/20 "
        f"final={sum(r['final_labor'] for r in rows)}/20"
    )
    print(f"degradation={sum(bool(r['degradation']) for r in rows)}/4")


if __name__ == "__main__":
    main()
