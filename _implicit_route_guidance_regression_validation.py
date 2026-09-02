"""A/B real-chain regression for implicit design-route guidance."""

from __future__ import annotations

from pathlib import Path
import re

import architect_chat as ac
from conversation_state import empty_state


OUT = Path(
    "../03_AI测试记录/项目日志/"
    "2026年8月24日_隐性设计路线引导_真实回归验证报告.md"
)

CASES = (
    ("开放与社区感", "我想做得开放、有社区感。你先帮我往下推一版，然后告诉我下一步需要判断什么。"),
    ("自然与通透", "我想让空间自然、通透一点，你先给一个可画起点，再告诉我接下来该判断什么。"),
    ("纪念馆仪式感", "这个纪念馆想有仪式感，但我还没有确定组织形式。你先帮我展开一版。"),
    ("用户提出公共主街", "我想试试公共主街这个方向，继续深化看看，最后告诉我下一步最该判断什么。"),
)

def implicit_route_hits(text: str, user_message: str) -> list[str]:
    source_forms = ac._candidate_route_forms(user_message)
    ai_forms = ac._candidate_route_forms(text) - source_forms
    hits = []
    for sentence in re.findall(r"[^。！？!?\n]+[？?]", text or ""):
        question_forms = ac._candidate_route_forms(sentence)
        question_uses_user_route = bool(question_forms & source_forms)
        names_unsourced = bool(
            question_forms - source_forms
        ) and not question_uses_user_route
        pronoun_choice = bool(
            ai_forms
            and not question_uses_user_route
            and ac._CANDIDATE_ROUTE_PRONOUN_RE.search(sentence)
            and ac._CANDIDATE_ROUTE_VARIANT_CHOICE_RE.search(sentence)
        )
        if names_unsourced or pronoun_choice:
            hits.append(sentence.strip())
    return hits


def design_labor(text: str) -> tuple[int, list[str]]:
    dimensions = {
        "功能关系": ("功能", "邻接", "公共区", "活动区", "门厅"),
        "空间骨架": ("骨架", "组织", "流线", "入口", "空间序列"),
        "体量/剖面": ("体量", "层", "围合", "展开", "剖面", "挑空"),
        "可画动作": ("画", "草图", "平面", "剖面", "标出", "可画"),
    }
    found = [name for name, terms in dimensions.items() if any(term in (text or "") for term in terms)]
    return len(found), found


def degradation(text: str) -> list[str]:
    result = []
    if any(term in (text or "") for term in ("无法判断", "信息不足，无法", "不能给出建议")):
        result.append("无法判断式退化")
    if any(term in (text or "") for term in ("内部检查结果", "Candidate Commitment Boundary", "修订后的完整方案")):
        result.append("内部规则外显")
    return result


def run_case(prompt: str, enabled: bool) -> dict:
    ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = enabled
    result = ac.chat_turn(prompt, [], empty_state(), turn_id=1, capture_stages=True)
    reply = result.get("reply") or ""
    stages = result.get("stages") or {}
    labor_score, labor_items = design_labor(reply)
    return {
        "reply": reply,
        "hits": implicit_route_hits(reply, prompt),
        "labor": labor_score,
        "labor_items": labor_items,
        "degradation": degradation(reply),
        "patched": bool(stages.get("candidate_route_question_patched")),
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

    a_hits = sum(len(row["a"]["hits"]) for row in rows)
    b_hits = sum(len(row["b"]["hits"]) for row in rows)
    a_labor = sum(row["a"]["labor"] for row in rows)
    b_labor = sum(row["b"]["labor"] for row in rows)
    a_deg = sum(bool(row["a"]["degradation"]) for row in rows)
    b_deg = sum(bool(row["b"]["degradation"]) for row in rows)
    patched = sum(row["b"]["patched"] for row in rows)
    if a_hits > b_hits and b_labor >= a_labor and b_deg <= a_deg:
        conclusion = "支持：隐性路线引导下降，设计劳动保持。"
    elif a_hits == 0 and b_hits == 0:
        conclusion = "机制回归通过，但真实 A 组未复现目标错误，下降效果证据不足。"
    else:
        conclusion = "不支持或仍有回归，需要结合逐案语义审阅。"

    lines = [
        "# 隐性设计路线引导真实回归验证报告",
        "",
        "日期：2026-08-24",
        "",
        "A 关闭 Candidate Commitment Boundary；B 开启。其余实验机制关闭，保留真实生成链原有检查。",
        "",
        "## 汇总",
        "",
        "|指标|A|B|",
        "|-|-:|-:|",
        f"|隐性路线引导|{a_hits}|{b_hits}|",
        f"|设计劳动|{a_labor}/16|{b_labor}/16|",
        f"|退化案例|{a_deg}/4|{b_deg}/4|",
        f"|末句局部改写|—|{patched}/4|",
        "",
        f"结论：{conclusion}",
        "",
    ]
    for row in rows:
        lines.extend((f"## {row['title']}", "", f"输入：{row['prompt']}", ""))
        for label in ("a", "b"):
            item = row[label]
            lines.extend((
                f"### {label.upper()} 组",
                "",
                f"隐性路线引导：{len(item['hits'])}；设计劳动：{item['labor']}/4（{'、'.join(item['labor_items']) or '无'}）；退化：{'、'.join(item['degradation']) or '无'}；末句改写：{'是' if item['patched'] else '否'}。",
                "",
                *( ["命中：" + "｜".join(item["hits"]), ""] if item["hits"] else [] ),
                item["reply"],
                "",
            ))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"report={OUT.resolve()}")
    print(f"implicit_route A={a_hits} B={b_hits}")
    print(f"design_labor A={a_labor}/16 B={b_labor}/16")
    print(f"degradation A={a_deg}/4 B={b_deg}/4")
    print(f"patched B={patched}/4")


if __name__ == "__main__":
    main()
