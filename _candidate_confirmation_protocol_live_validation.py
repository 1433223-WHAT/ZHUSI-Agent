"""Real-chain validation for Candidate confirmation and rejection transitions."""

from __future__ import annotations

from pathlib import Path
import re

import architect_chat as ac
from conversation_state import empty_state


OUT = Path(
    "../03_AI测试记录/项目日志/"
    "2026年8月24日_Candidate_确认协议_多轮真实验证报告.md"
)

CONVERSATIONS = (
    {
        "title": "候选转明确确认",
        "turns": (
            "我觉得中央中庭这个方向不错，可以继续看看，但先不要定死。",
            "那就按这个做。中央中庭方案定了，请继续深化入口、流线和剖面。",
            "继续把首层公共空间和二层关系推到可画草图的程度。",
        ),
        "expected_status": ("candidate", "confirmed", "none"),
        "route": "中庭",
    },
    {
        "title": "候选转明确拒绝",
        "turns": (
            "我觉得中央中庭这个方向挺有意思，继续深化看看，但还没确定。",
            "这个方向不要了，换一个不依赖中庭的线性公共街道方向。",
            "沿新的线性公共街道方向继续展开入口、流线和剖面，但先作为候选。",
        ),
        "expected_status": ("candidate", "rejected", "candidate"),
        "route": "中庭",
    },
)

DEMOTION_RE = re.compile(r"非你的决定|不是你的决定|尚未确认|还未确认|未确认采用|不是定案")
LEAK_RE = re.compile(r"内部检查结果|修订后的完整方案|candidate_commitment|身份检查")
OLD_ROUTE_ACTIVE_RE = re.compile(
    r"中庭.{0,16}(?:继续作为|仍作为|保留为|作为当前|作为方案|是当前|继续深化|确定为)|"
    r"(?:继续作为|仍作为|保留为|作为当前|作为方案|继续深化|确定为).{0,12}中庭"
)
LABOR_TERMS = ("入口", "流线", "公共空间", "空间关系", "剖面", "体量", "草图", "画")


def _labor(text: str) -> int:
    return sum(term in (text or "") for term in LABOR_TERMS)


def _old_route_recurrence(text: str) -> bool:
    return bool(OLD_ROUTE_ACTIVE_RE.search(text or ""))


def _run_conversation(spec: dict) -> list[dict]:
    state = empty_state()
    history: list[dict] = []
    rows = []
    for turn, user_message in enumerate(spec["turns"], start=1):
        result = ac.chat_turn(
            user_message,
            history,
            state,
            turn_id=turn,
            capture_stages=True,
        )
        reply = result.get("reply") or ""
        stages = result.get("stages") or {}
        rows.append({
            "turn": turn,
            "user": user_message,
            "reply": reply,
            "status": stages.get("candidate_commitment_status", "missing"),
            "expected": spec["expected_status"][turn - 1],
            "demotion": bool(DEMOTION_RE.search(reply)) if spec["title"] == "候选转明确确认" and turn == 2 else False,
            "leak": bool(LEAK_RE.search(reply)),
            "old_route_recurrence": _old_route_recurrence(reply) if spec["title"] == "候选转明确拒绝" and turn >= 2 else False,
            "labor": _labor(reply),
        })
        history.extend((
            {"role": "user", "content": user_message},
            {"role": "assistant", "content": reply},
        ))
        state = result.get("state") or state
    return rows


def _write_report(results: dict[str, list[dict]]) -> None:
    rows = [row for conversation in results.values() for row in conversation]
    status_errors = sum(row["status"] != row["expected"] for row in rows)
    demotions = sum(row["demotion"] for row in rows)
    leaks = sum(row["leak"] for row in rows)
    recurrences = sum(row["old_route_recurrence"] for row in rows)
    labor = sum(row["labor"] for row in rows)
    supported = not any((status_errors, demotions, leaks, recurrences)) and labor >= 18

    lines = [
        "# Candidate 确认协议多轮真实验证报告",
        "",
        "## 范围",
        "",
        "只验证候选、明确确认和明确拒绝的转换；Candidate Commitment Boundary 开启，Experience Boundary、Experience Patch、PIL、Design State 关闭。",
        "",
        "## 汇总",
        "",
        "|指标|结果|",
        "|-|-:|",
        f"|状态识别错误|{status_errors}/6|",
        f"|明确决定被降级|{demotions}/1|",
        f"|拒绝后旧路线复发|{recurrences}/2|",
        f"|内部检查外显|{leaks}/6|",
        f"|设计劳动命中|{labor}/48|",
        "",
        f"结论：{'支持，Candidate 当前修复可先冻结。' if supported else '不支持，仍有需要修复的回归。'}",
        "",
    ]
    for title, conversation in results.items():
        lines.extend((f"## {title}", ""))
        for row in conversation:
            lines.extend((
                f"### Turn {row['turn']}",
                "",
                f"用户：{row['user']}",
                "",
                f"状态：{row['status']}（预期 {row['expected']}）；决定降级：{'是' if row['demotion'] else '否'}；旧路线复发：{'是' if row['old_route_recurrence'] else '否'}；外显：{'是' if row['leak'] else '否'}；设计劳动：{row['labor']}/8。",
                "",
                "回答：",
                "",
                row["reply"],
                "",
            ))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    old = {
        "candidate": ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY,
        "experience": ac.ENABLE_EXPERIENCE_BOUNDARY,
        "patch": ac.ENABLE_EXPERIENCE_PATCH_EXECUTION,
        "pil": ac.ENABLE_PIL_MIDDLEWARE,
        "design_state": ac.ENABLE_DESIGN_STATE_SUMMARY,
    }
    try:
        ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = True
        ac.ENABLE_EXPERIENCE_BOUNDARY = False
        ac.ENABLE_EXPERIENCE_PATCH_EXECUTION = False
        ac.ENABLE_PIL_MIDDLEWARE = False
        ac.ENABLE_DESIGN_STATE_SUMMARY = False
        results = {spec["title"]: _run_conversation(spec) for spec in CONVERSATIONS}
        _write_report(results)
        print(f"report={OUT.resolve()}")
    finally:
        ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = old["candidate"]
        ac.ENABLE_EXPERIENCE_BOUNDARY = old["experience"]
        ac.ENABLE_EXPERIENCE_PATCH_EXECUTION = old["patch"]
        ac.ENABLE_PIL_MIDDLEWARE = old["pil"]
        ac.ENABLE_DESIGN_STATE_SUMMARY = old["design_state"]


if __name__ == "__main__":
    main()
