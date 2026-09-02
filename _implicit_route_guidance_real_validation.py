"""Real-chain A/B validation for implicit route-guidance control."""

from __future__ import annotations

from pathlib import Path
import re

import architect_chat as ac
from conversation_state import empty_state


OUT = Path("../03_AI测试记录/项目日志/2026年8月24日_Candidate_Boundary_正文承诺修复_真实验证报告.md")

CASES = [
    (
        "抽象开放目标",
        "我想做一个更开放、更有社区感的文化中心，你先帮我往下推一个空间方向。",
    ),
    (
        "中庭倾向未确认",
        "我觉得中央中庭挺有意思，可以继续深化看看。",
    ),
    (
        "北侧入口候选",
        "入口放北侧是不是更好？",
    ),
    (
        "抽象自然与通透目标",
        "我想让空间更自然、通透一点，你先给一版可画骨架。",
    ),
]

ROUTE_PATTERNS = [
    r"(?:这个|该)(?:中庭|庭院).{0,24}(?:是|做成).{0,16}(?:还是|或者)",
    r"(?:中庭|庭院).{0,18}(?:环绕|穿越|集中|分散).{0,18}(?:还是|或者)",
    r"先按.{0,16}(?:中庭|庭院|线性街道|核心大厅|核心组织).{0,16}(?:继续|深化|试)",
    r"(?:开放|社区感|自然|通透|仪式感).{0,16}(?:就是|意味着|等于).{0,16}(?:中庭|庭院|线性街道|核心大厅)",
    r"(?:只能|就按|必须选择|直接选择).{0,16}(?:中庭|庭院|线性|北侧入口)",
]

FIXATION_PATTERNS = [
    r"你的方案(?:采用|确定|选择)",
    r"(?:确定|正式)采用.{0,16}(?:中庭|庭院|北侧入口|线性)",
    r"(?:主入口|入口).{0,8}(?:应该|必须|就).{0,8}放在北侧",
    r"(?:中庭|庭院|北侧入口).{0,16}(?:已经确定|作为既定|是当前方案)",
]


def pattern_hits(text: str, patterns: list[str]) -> list[str]:
    return [pattern for pattern in patterns if re.search(pattern, text)]


def design_labor(text: str) -> tuple[int, list[str]]:
    dimensions = {
        "功能关系": ("功能", "邻接", "公共区", "活动区", "门厅"),
        "空间骨架": ("骨架", "组织", "流线", "入口", "空间序列"),
        "体量方向": ("体量", "层", "围合", "展开", "剖面"),
        "可画动作": ("画", "草图", "平面", "剖面", "标出", "可画"),
    }
    found = [name for name, terms in dimensions.items() if any(term in text for term in terms)]
    return len(found), found


def degradation(text: str) -> list[str]:
    found = []
    if any(term in text for term in ("无法判断", "信息不足，无法", "不能给出建议")):
        found.append("无法判断式退化")
    if any(term in text for term in (
        "Candidate Commitment Boundary", "内部生成前约束", "内部检查结果",
        "检查结果如下", "证据核查", "一致性核查", "作用范围核查",
    )):
        found.append("内部规则外显")
    if text.count("需要确认") + text.count("需要验证") >= 6:
        found.append("条件句膨胀")
    return found


def run_case(prompt: str, enabled: bool) -> dict:
    ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = enabled
    result = ac.chat_turn(prompt, [], empty_state(), turn_id=1, capture_stages=True)
    stages = result.get("stages") or {}
    raw = stages.get("raw_draft") or ""
    checked = stages.get("checked_draft") or ""
    final = stages.get("final_after_boundary") or result.get("reply") or ""
    labor_score, labor_items = design_labor(final)
    return {
        "final": final,
        "raw": raw,
        "checked": checked,
        "body_commitment_patched": bool(stages.get("candidate_commitment_body_patched")),
        "route_question_patched": bool(stages.get("candidate_route_question_patched")),
        "route_hits": pattern_hits(final, ROUTE_PATTERNS),
        "fixation_hits": pattern_hits(final, FIXATION_PATTERNS),
        "labor_score": labor_score,
        "labor_items": labor_items,
        "degradation": degradation(final),
    }


def main() -> None:
    old = {
        "candidate": ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY,
        "experience": ac.ENABLE_EXPERIENCE_BOUNDARY,
        "patch": ac.ENABLE_EXPERIENCE_PATCH_EXECUTION,
        "pil": ac.ENABLE_PIL_MIDDLEWARE,
        "design_state": ac.ENABLE_DESIGN_STATE_SUMMARY,
        "preoutput": ac.ENABLE_PREOUTPUT_CHECK,
    }
    rows = []
    try:
        ac.ENABLE_EXPERIENCE_BOUNDARY = False
        ac.ENABLE_EXPERIENCE_PATCH_EXECUTION = False
        ac.ENABLE_PIL_MIDDLEWARE = False
        ac.ENABLE_DESIGN_STATE_SUMMARY = False
        ac.ENABLE_PREOUTPUT_CHECK = True
        for title, prompt in CASES:
            rows.append({
                "title": title,
                "prompt": prompt,
                "a": run_case(prompt, False),
                "b": run_case(prompt, True),
            })
    finally:
        ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = old["candidate"]
        ac.ENABLE_EXPERIENCE_BOUNDARY = old["experience"]
        ac.ENABLE_EXPERIENCE_PATCH_EXECUTION = old["patch"]
        ac.ENABLE_PIL_MIDDLEWARE = old["pil"]
        ac.ENABLE_DESIGN_STATE_SUMMARY = old["design_state"]
        ac.ENABLE_PREOUTPUT_CHECK = old["preoutput"]

    a_route = sum(len(row["a"]["route_hits"]) for row in rows)
    b_route = sum(len(row["b"]["route_hits"]) for row in rows)
    a_fix = sum(len(row["a"]["fixation_hits"]) for row in rows)
    b_fix = sum(len(row["b"]["fixation_hits"]) for row in rows)
    a_labor = sum(row["a"]["labor_score"] for row in rows)
    b_labor = sum(row["b"]["labor_score"] for row in rows)
    a_deg = sum(bool(row["a"]["degradation"]) for row in rows)
    b_deg = sum(bool(row["b"]["degradation"]) for row in rows)
    b_body_patched = sum(row["b"]["body_commitment_patched"] for row in rows)
    b_patched = sum(row["b"]["route_question_patched"] for row in rows)

    if a_route > b_route and b_labor >= a_labor and b_deg <= a_deg:
        conclusion = "支持：隐性路线引导下降，设计劳动保持，未增加退化。"
    elif a_route == 0:
        conclusion = "证据不足：本轮 A 组未复现隐性路线引导，不能证明修复带来下降；需结合逐案语义审阅。"
    else:
        conclusion = "部分支持或不支持：需要结合逐案原文判断，当前自动指标未同时满足下降与劳动保持。"

    lines = [
        "# Candidate Boundary 正文承诺修复真实验证报告",
        "",
        "日期：2026-08-24",
        "",
        "## 验证设置",
        "",
        "A 组关闭 Candidate Commitment Boundary；B 组开启。Experience Boundary、Experience Patch、PIL、Design State 均关闭，保留当前真实链的原有输出检查。",
        "",
        "## 自动指标汇总",
        "",
        f"- 隐性路线引导模式命中：A={a_route}，B={b_route}",
        f"- 候选固化模式命中：A={a_fix}，B={b_fix}",
        f"- 设计劳动：A={a_labor}/16，B={b_labor}/16",
        f"- 退化案例：A={a_deg}/4，B={b_deg}/4",
        f"- B 组正文承诺局部改写：{b_body_patched}/4",
        f"- B 组末句路线问题局部改写：{b_patched}/4",
        "",
        "自动模式只用于定位，最终判断必须结合下面的完整回答做语义审阅。",
        "",
        "## 初步结论",
        "",
        conclusion,
        "",
    ]
    for row in rows:
        lines.extend([
            f"## {row['title']}",
            "",
            f"输入：{row['prompt']}",
            "",
            f"A：路线引导={len(row['a']['route_hits'])}，候选固化={len(row['a']['fixation_hits'])}，设计劳动={row['a']['labor_score']}/4（{'、'.join(row['a']['labor_items']) or '无'}），退化={'、'.join(row['a']['degradation']) or '无'}。",
            "",
            "### A 输出",
            "",
            row["a"]["final"],
            "",
            f"B：路线引导={len(row['b']['route_hits'])}，候选固化={len(row['b']['fixation_hits'])}，设计劳动={row['b']['labor_score']}/4（{'、'.join(row['b']['labor_items']) or '无'}），退化={'、'.join(row['b']['degradation']) or '无'}。",
            f"正文承诺局部改写：{'是' if row['b']['body_commitment_patched'] else '否'}。",
            f"末句路线问题局部改写：{'是' if row['b']['route_question_patched'] else '否'}。",
            "",
            "### B 输出",
            "",
            row["b"]["final"],
            "",
            "### B 链路诊断",
            "",
            f"Generator 原稿与隐藏检查后文本是否不同：{'是' if row['b']['raw'] != row['b']['checked'] else '否'}。",
            "",
            "#### B Generator 原稿",
            "",
            row["b"]["raw"],
            "",
        ])

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"report={OUT.resolve()}")
    print(f"route_guidance A={a_route} B={b_route}")
    print(f"candidate_fixation A={a_fix} B={b_fix}")
    print(f"design_labor A={a_labor}/16 B={b_labor}/16")
    print(f"degradation A={a_deg}/4 B={b_deg}/4")
    print(f"body_commitment_patched B={b_body_patched}/4")
    print(f"route_question_patched B={b_patched}/4")


if __name__ == "__main__":
    main()
