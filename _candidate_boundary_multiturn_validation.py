"""Multi-turn real-chain validation for Candidate Commitment Boundary."""

from __future__ import annotations

from pathlib import Path
import re

import architect_chat as ac
from conversation_state import empty_state


OUT = Path(
    "../03_AI测试记录/项目日志/"
    "2026年8月24日_Candidate_Boundary_多轮真实验证报告.md"
)

CONVERSATIONS = [
    {
        "title": "中央中庭候选",
        "turns": [
            "我觉得中央中庭挺有意思，可以继续深化看看，但我还没有决定采用。",
            "按这个候选方向再推一版入口、流线和剖面，但仍然先不要拍板。",
            "我不想要中庭了，请收回这个方向，换一个不依赖中庭的空间骨架。",
        ],
        "route_terms": ["中央中庭", "中庭"],
        "labor_terms": ["入口", "流线", "空间", "体量", "剖面", "画"],
    },
    {
        "title": "北侧入口候选",
        "turns": [
            "北侧入口是不是更好？先作为候选帮我推推，但我还没有决定。",
            "这个方向听起来不错，继续深化入口前场和公共空间，但还没拍板。",
            "我决定不采用北侧主入口。请收回它，改为比较东侧和西侧入口。",
        ],
        "route_terms": ["北侧入口", "北侧主入口", "主入口放在北侧"],
        "labor_terms": ["入口", "前场", "公共空间", "流线", "体量", "画"],
    },
]

COMMITMENT_RE = re.compile(
    r"确定采用|已经确定|方案采用|你的方案(?:采用|是)|当前方案(?:采用|确定)|"
    r"最终选择|就按.{0,16}(?:中庭|北侧入口|北侧主入口)|"
    r"(?:中庭|北侧入口|北侧主入口).{0,16}(?:已经确定|正式确定|作为最终方案)"
)
RETRACTION_RE = re.compile(r"收回|不采用|不想要|不依赖|没有中庭|无中庭|拒绝|放弃|取消|不再|不是|未确定|还没|不要拍板")
CONDITIONAL_RE = re.compile(r"候选|可以|可能|如果|尝试|测试|暂定|未确认|保留调整|可修改|可放弃")


def _candidate_fixation_hits(text: str) -> list[str]:
    hits = []
    for sentence in re.findall(r"[^。！？\n]+(?:[。！？]|$)", text or ""):
        if (
            COMMITMENT_RE.search(sentence)
            and not RETRACTION_RE.search(sentence)
            and not CONDITIONAL_RE.search(sentence)
        ):
            hits.append(sentence.strip())
    return hits


def _rejected_route_hits(text: str, route_terms: list[str]) -> list[str]:
    hits = []
    for sentence in re.findall(r"[^。！？\n]+(?:[。！？]|$)", text or ""):
        if RETRACTION_RE.search(sentence):
            continue
        for term in route_terms:
            if term in sentence and re.search(r"采用|保留|继续|作为|确定|主线|骨架", sentence):
                hits.append(sentence.strip())
                break
    return hits


def _labor(text: str, terms: list[str]) -> int:
    return sum(term in (text or "") for term in terms)


def _degradation(text: str) -> list[str]:
    result = []
    if any(term in (text or "") for term in ("无法判断", "信息不足", "不能给出建议")):
        result.append("无法判断式退化")
    if any(term in (text or "") for term in ("内部检查结果", "candidate_commitment", "身份检查")):
        result.append("内部检查外显")
    return result


def _run_conversation(conversation: dict, enabled: bool) -> list[dict]:
    state = empty_state()
    history = []
    rows = []
    for turn_id, user_message in enumerate(conversation["turns"], start=1):
        result = ac.chat_turn(
            user_message,
            history,
            state,
            turn_id=turn_id,
            capture_stages=True,
        )
        reply = result.get("reply") or ""
        stages = result.get("stages") or {}
        rows.append({
            "turn": turn_id,
            "user": user_message,
            "reply": reply,
            "fixation": _candidate_fixation_hits(reply) if turn_id < 3 else [],
            "rejected": _rejected_route_hits(reply, conversation["route_terms"]) if turn_id == 3 else [],
            "labor": _labor(reply, conversation["labor_terms"]),
            "degradation": _degradation(reply),
            "question_patched": bool(stages.get("candidate_route_question_patched")),
        })
        history.extend([
            {"role": "user", "content": user_message},
            {"role": "assistant", "content": reply},
        ])
        state = result.get("state") or state
    return rows


def _run_group(enabled: bool) -> dict[str, list[dict]]:
    old = {
        "candidate": ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY,
        "experience": ac.ENABLE_EXPERIENCE_BOUNDARY,
        "patch": ac.ENABLE_EXPERIENCE_PATCH_EXECUTION,
        "pil": ac.ENABLE_PIL_MIDDLEWARE,
        "design_state": ac.ENABLE_DESIGN_STATE_SUMMARY,
    }
    try:
        ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = enabled
        ac.ENABLE_EXPERIENCE_BOUNDARY = False
        ac.ENABLE_EXPERIENCE_PATCH_EXECUTION = False
        ac.ENABLE_PIL_MIDDLEWARE = False
        ac.ENABLE_DESIGN_STATE_SUMMARY = False
        return {
            conversation["title"]: _run_conversation(conversation, enabled)
            for conversation in CONVERSATIONS
        }
    finally:
        ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = old["candidate"]
        ac.ENABLE_EXPERIENCE_BOUNDARY = old["experience"]
        ac.ENABLE_EXPERIENCE_PATCH_EXECUTION = old["patch"]
        ac.ENABLE_PIL_MIDDLEWARE = old["pil"]
        ac.ENABLE_DESIGN_STATE_SUMMARY = old["design_state"]


def _totals(group: dict[str, list[dict]]) -> dict:
    rows = [row for conversation in group.values() for row in conversation]
    return {
        "fixation": sum(len(row["fixation"]) for row in rows),
        "rejected": sum(len(row["rejected"]) for row in rows),
        "labor": sum(row["labor"] for row in rows),
        "degradation": sum(bool(row["degradation"]) for row in rows),
        "question_patched": sum(row["question_patched"] for row in rows),
    }


def _write_report(a_group: dict, b_group: dict) -> None:
    a = _totals(a_group)
    b = _totals(b_group)
    supported = (
        b["fixation"] < a["fixation"]
        and b["rejected"] <= a["rejected"]
        and b["labor"] >= a["labor"]
        and b["degradation"] <= a["degradation"]
    )
    lines = [
        "# Candidate Commitment Boundary 多轮真实验证报告",
        "",
        "## 设置",
        "",
        "A 关闭 Candidate Boundary；B 开启 Candidate Boundary。Experience Patch、Experience Boundary、PIL、Design State 均关闭。每组连续测试候选提出、未确认深化、明确否定。",
        "",
        "## 汇总",
        "",
        "|指标|A|B|",
        "|-|-:|-:|",
        f"|候选固化|{a['fixation']}|{b['fixation']}|",
        f"|否定后旧路线复发|{a['rejected']}|{b['rejected']}|",
        f"|设计劳动|{a['labor']}/36|{b['labor']}/36|",
        f"|退化轮次|{a['degradation']}/6|{b['degradation']}/6|",
        f"|末句路线问题局部改写|—|{b['question_patched']}/6|",
        "",
        f"结论：{'支持' if supported else '不支持或证据不足'}。",
        "",
    ]
    for conversation in CONVERSATIONS:
        title = conversation["title"]
        lines.extend([f"## {title}", ""])
        for label, group in (("A", a_group), ("B", b_group)):
            lines.extend([f"### {label} 组", ""])
            for row in group[title]:
                lines.extend([
                    f"#### Turn {row['turn']}",
                    "",
                    f"用户：{row['user']}",
                    "",
                    f"候选固化：{len(row['fixation'])}；旧路线复发：{len(row['rejected'])}；设计劳动：{row['labor']}/6；退化：{('、'.join(row['degradation']) if row['degradation'] else '无')}；末句改写：{'是' if row['question_patched'] else '否'}。",
                    "",
                    "回答：",
                    "",
                    row["reply"],
                    "",
                ])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    a_group = _run_group(False)
    b_group = _run_group(True)
    _write_report(a_group, b_group)
    print(f"report={OUT.resolve()}")
    print(f"A={_totals(a_group)}")
    print(f"B={_totals(b_group)}")


if __name__ == "__main__":
    main()
