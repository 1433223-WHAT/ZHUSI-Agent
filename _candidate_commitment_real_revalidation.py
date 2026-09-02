"""Real-chain recurrence check for the annotated Candidate Boundary repair."""

from __future__ import annotations

from pathlib import Path
import re

import architect_chat as ac
from conversation_state import empty_state


OUT = Path(
    "../03_AI测试记录/项目日志/"
    "2026年8月24日_Candidate_Boundary_真实错误复发检查报告.md"
)

CASES = (
    (
        "北侧道路入口候选",
        "基地北侧临城市道路，南侧住宅。入口放北侧是不是更好？",
        True,
    ),
    (
        "北侧入口轻度倾向",
        "我觉得北侧入口可能更合适，但还没决定，你继续推推看。",
        True,
    ),
    (
        "中庭候选未确认",
        "我觉得中央中庭挺不错，但还没最终决定，你继续深化看看。",
        True,
    ),
    (
        "中庭已明确确认",
        "我已经决定采用中央中庭组织方式，请继续深化入口和流线。",
        False,
    ),
)

_CERTAINTY_RE = re.compile(
    r"方向是对的|确实更合理|确实更符合|你的方案采用|确定采用|主入口应该"
)
_CONDITIONAL_RE = re.compile(r"如果|假如|前提|待验证|缺少|不能据此|取决于")


def certainty_hits(text: str) -> list[str]:
    hits = []
    for sentence in re.split(r"[。！？!?\n]", text or ""):
        if _CONDITIONAL_RE.search(sentence):
            continue
        hits.extend(match.group(0) for match in _CERTAINTY_RE.finditer(sentence))
    return hits


def design_labor(text: str) -> tuple[int, list[str]]:
    dimensions = {
        "功能关系": ("功能", "邻接", "门厅", "公共区"),
        "空间骨架": ("骨架", "组织", "流线", "入口", "空间序列"),
        "体量策略": ("体量", "剖面", "层", "围合", "展开"),
        "可画动作": ("画", "草图", "平面", "剖面", "标出"),
    }
    found = [name for name, terms in dimensions.items() if any(term in text for term in terms)]
    return len(found), found


def degradation(text: str) -> list[str]:
    found = []
    if any(term in text for term in ("无法判断", "信息不足，无法", "不能给出建议")):
        found.append("停止推进")
    if any(term in text for term in ("Candidate Commitment Boundary", "内部生成前约束", "内部检查结果")):
        found.append("内部规则外显")
    if text.count("需要确认") + text.count("需要验证") >= 6:
        found.append("条件膨胀")
    return found


def run_case(prompt: str, enabled: bool) -> dict:
    ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = enabled
    result = ac.chat_turn(prompt, [], empty_state(), turn_id=1, capture_stages=True)
    stages = result.get("stages") or {}
    final = stages.get("final_after_boundary") or result.get("reply") or ""
    labor_score, labor_items = design_labor(final)
    return {
        "final": final,
        "certainty_hits": certainty_hits(final),
        "labor_score": labor_score,
        "labor_items": labor_items,
        "degradation": degradation(final),
        "body_patched": bool(stages.get("candidate_commitment_body_patched")),
        "question_patched": bool(stages.get("candidate_route_question_patched")),
    }


def main() -> None:
    old = {
        "candidate": ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY,
        "experience": ac.ENABLE_EXPERIENCE_BOUNDARY,
        "patch": ac.ENABLE_EXPERIENCE_PATCH_EXECUTION,
        "pil": ac.ENABLE_PIL_MIDDLEWARE,
        "design_state": ac.ENABLE_DESIGN_STATE_SUMMARY,
    }
    rows = []
    try:
        ac.ENABLE_EXPERIENCE_BOUNDARY = False
        ac.ENABLE_EXPERIENCE_PATCH_EXECUTION = False
        ac.ENABLE_PIL_MIDDLEWARE = False
        ac.ENABLE_DESIGN_STATE_SUMMARY = False
        for title, prompt, candidate_expected in CASES:
            rows.append({
                "title": title,
                "prompt": prompt,
                "candidate_expected": candidate_expected,
                "a": run_case(prompt, False),
                "b": run_case(prompt, True),
            })
    finally:
        ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = old["candidate"]
        ac.ENABLE_EXPERIENCE_BOUNDARY = old["experience"]
        ac.ENABLE_EXPERIENCE_PATCH_EXECUTION = old["patch"]
        ac.ENABLE_PIL_MIDDLEWARE = old["pil"]
        ac.ENABLE_DESIGN_STATE_SUMMARY = old["design_state"]

    candidate_rows = [row for row in rows if row["candidate_expected"]]
    a_hits = sum(len(row["a"]["certainty_hits"]) for row in candidate_rows)
    b_hits = sum(len(row["b"]["certainty_hits"]) for row in candidate_rows)
    a_labor = sum(row["a"]["labor_score"] for row in rows)
    b_labor = sum(row["b"]["labor_score"] for row in rows)
    a_degradation = sum(bool(row["a"]["degradation"]) for row in rows)
    b_degradation = sum(bool(row["b"]["degradation"]) for row in rows)
    body_patched = sum(row["b"]["body_patched"] for row in candidate_rows)

    lines = [
        "# Candidate Boundary 真实错误复发检查报告",
        "",
        "日期：2026-08-24",
        "",
        "## 设置",
        "",
        "A 关闭 Candidate Commitment Boundary；B 开启。其他实验层关闭。前三例为 Candidate，第四例为学生明确确认控制组。",
        "",
        "## 自动定位",
        "",
        f"- Candidate 无条件确定表达：A={a_hits}，B={b_hits}。",
        f"- 设计劳动：A={a_labor}/16，B={b_labor}/16。",
        f"- 退化案例：A={a_degradation}/4，B={b_degradation}/4。",
        f"- B 正文局部修正触发：{body_patched}/3。",
        "",
        "自动指标只定位原文，最终结论需结合逐案语义复核。",
        "",
    ]
    for row in rows:
        lines.extend([
            f"## {row['title']}",
            "",
            f"输入：{row['prompt']}",
            "",
            f"A：确定表达={row['a']['certainty_hits'] or '无'}；设计劳动={row['a']['labor_score']}/4；退化={row['a']['degradation'] or '无'}。",
            "",
            "### A 输出",
            "",
            row["a"]["final"],
            "",
            f"B：确定表达={row['b']['certainty_hits'] or '无'}；设计劳动={row['b']['labor_score']}/4；退化={row['b']['degradation'] or '无'}；正文修正={'是' if row['b']['body_patched'] else '否'}；问题修正={'是' if row['b']['question_patched'] else '否'}。",
            "",
            "### B 输出",
            "",
            row["b"]["final"],
            "",
        ])

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"report={OUT.resolve()}")
    print(f"candidate_certainty A={a_hits} B={b_hits}")
    print(f"design_labor A={a_labor}/16 B={b_labor}/16")
    print(f"degradation A={a_degradation}/4 B={b_degradation}/4")
    print(f"body_patched B={body_patched}/3")


if __name__ == "__main__":
    main()
