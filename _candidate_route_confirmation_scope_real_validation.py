"""Real-chain validation for default-route and confirmation-scope repairs."""

from __future__ import annotations

from pathlib import Path
import re

import architect_chat as ac
from conversation_state import empty_state


OUT = Path(
    "../03_AI测试记录/项目日志/"
    "2026年8月25日_隐性默认路线与确认范围_真实修复验证报告.md"
)

CONVERSATIONS = (
    {
        "title": "悬置入口后的默认路线复发",
        "turns": (
            "基地北侧是支路，东侧是公园。我只考虑一个入口，但入口放北侧还是东侧还没决定。请先比较两个候选，不要默认任何一侧。",
            "我不想要双入口这个候选。继续推单入口和公园联系，但证据不足时仍不要默认北侧或东侧。给我可画动作，不要替我选。",
        ),
    },
    {
        "title": "确认决定的推导范围",
        "turns": (
            (
                "我做一个3600㎡青年社区文化中心，功能包括咖啡、展览、小剧场、舞蹈教室、"
                "社区会议室和办公后勤。我明确确认：我决定采用东侧单入口、连续公共带和局部通高。"
                "这三项是当前决定。"
            ),
            "请基于三项决定整理两层空间骨架、流线、体量和剖面。咖啡展览位置、剧场位置、后勤入口、公共带方向、两段式体量和二层走廊都没有确认。不要提问。",
        ),
    },
)

DEFAULT_ROUTE_RE = re.compile(
    r"先按.{0,40}(?:北侧|东侧).{0,24}(?:推|画|做|试)|"
    r"(?:北侧|东侧).{0,24}(?:默认|优先方案|当前路线)"
)
DERIVED_TERMS = ("咖啡", "展览", "剧场", "后勤", "直线", "两段式", "二层走廊")
LABOR_TERMS = ("功能", "空间骨架", "流线", "体量", "剖面", "可画", "草图")


def _derived_confirmation_hits(text: str) -> list[str]:
    hits = []
    in_confirmed_section = False
    for line in (text or "").splitlines():
        stripped = line.strip()
        if re.search(r"已确认(?:决定|部分)", stripped):
            in_confirmed_section = True
            continue
        if in_confirmed_section and (
            stripped == "---"
            or re.match(r"^#{1,6}\s", stripped)
            or (stripped.startswith("**") and "确认" not in stripped)
        ):
            in_confirmed_section = False
        if in_confirmed_section:
            for term in DERIVED_TERMS:
                if term in stripped:
                    hits.append(stripped)
                    break
        if any(term in stripped for term in DERIVED_TERMS) and re.search(
            r"已确认|\(确认\)|（确认）", stripped
        ):
            hits.append(stripped)
    return list(dict.fromkeys(hits))


def _run(spec: dict) -> list[dict]:
    state = empty_state()
    history: list[dict] = []
    rows = []
    for turn, message in enumerate(spec["turns"], start=1):
        result = ac.chat_turn(
            message,
            history,
            state,
            turn_id=turn,
            capture_stages=True,
        )
        reply = result.get("reply") or ""
        stages = result.get("stages") or {}
        state = result.get("state") or state
        rows.append({
            "turn": turn,
            "user": message,
            "reply": reply,
            "candidate_status": stages.get("candidate_commitment_status", "missing"),
            "body_patched": bool(stages.get("candidate_commitment_body_patched")),
            "default_route_hits": DEFAULT_ROUTE_RE.findall(reply),
            "derived_confirmation_hits": _derived_confirmation_hits(reply),
            "labor": sum(term in reply for term in LABOR_TERMS),
            "student_decisions": len(state.get("student_decisions") or []),
        })
        history.extend((
            {"role": "user", "content": message},
            {"role": "assistant", "content": reply},
        ))
    return rows


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
        results = {spec["title"]: _run(spec) for spec in CONVERSATIONS}
    finally:
        ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = old["candidate"]
        ac.ENABLE_EXPERIENCE_BOUNDARY = old["experience"]
        ac.ENABLE_EXPERIENCE_PATCH_EXECUTION = old["patch"]
        ac.ENABLE_PIL_MIDDLEWARE = old["pil"]
        ac.ENABLE_DESIGN_STATE_SUMMARY = old["design_state"]

    rows = [row for conversation in results.values() for row in conversation]
    default_hits = sum(len(row["default_route_hits"]) for row in rows)
    derived_hits = sum(len(row["derived_confirmation_hits"]) for row in rows)
    labor = sum(row["labor"] for row in rows)
    lines = [
        "# 隐性默认路线与确认范围真实修复验证报告",
        "",
        "日期：2026-08-25",
        "",
        "## 汇总",
        "",
        f"- 隐性默认路线自动命中：{default_hits}",
        f"- 推导细节被标为确认：{derived_hits}",
        f"- 设计劳动命中：{labor}/28",
        "- Candidate Commitment Boundary 开启；Experience Boundary、PIL、Design State 关闭。",
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
                f"candidate_status={row['candidate_status']}；student_decisions={row['student_decisions']}；"
                f"默认路线命中={len(row['default_route_hits'])}；推导确认命中={len(row['derived_confirmation_hits'])}；"
                f"设计劳动={row['labor']}/7；正文修正={'是' if row['body_patched'] else '否'}。",
                "",
                "回答：",
                "",
                row["reply"],
                "",
            ))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"report={OUT.resolve()}")
    print(f"default_route_hits={default_hits}")
    print(f"derived_confirmation_hits={derived_hits}")
    print(f"design_labor={labor}/28")


if __name__ == "__main__":
    main()
