"""Targeted real-chain rerun of the topology-rejection turn."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import re

import architect_chat as ac
from conversation_state import empty_state, update_state


SOURCE = Path(
    "../03_AI测试记录/项目日志/"
    "2026年8月31日_候选路线语义复发修复后真实复测.md"
)
OUT = Path(
    "../03_AI测试记录/项目日志/"
    f"{datetime.now().year}年{datetime.now().month}月{datetime.now().day}日_"
    f"候选路线第6轮定向真实复测_{datetime.now().strftime('%H%M%S')}.md"
)


def _rows() -> list[dict]:
    pattern = re.compile(
        r"## 第 (?P<turn>\d+) 轮\n\n"
        r"\*\*学生：\*\* (?P<user>.*?)\n\n"
        r"\*\*筑思 Agent：\*\*\n\n(?P<reply>.*?)\n\n"
        r"内部记录：",
        re.DOTALL,
    )
    return [
        {
            "turn": int(match.group("turn")),
            "user": match.group("user").strip(),
            "reply": match.group("reply").strip(),
        }
        for match in pattern.finditer(SOURCE.read_text(encoding="utf-8"))
    ]


def main() -> None:
    rows = _rows()
    if len(rows) < 6:
        raise RuntimeError("saved real transcript must contain six turns")
    prior = rows[:5]
    message = rows[5]["user"]
    history: list[dict] = []
    state = empty_state()
    for row in prior:
        state = update_state(state, row["user"], row["turn"])
        state.setdefault("interaction_log", []).append({
            "turn_id": row["turn"],
            "student_message": row["user"],
            "ai_reply": row["reply"],
        })
        history.extend((
            {"role": "user", "content": row["user"]},
            {"role": "assistant", "content": row["reply"]},
        ))

    flags = {
        "candidate": ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY,
        "experience": ac.ENABLE_EXPERIENCE_BOUNDARY,
        "patch": ac.ENABLE_EXPERIENCE_PATCH_EXECUTION,
        "preoutput": ac.ENABLE_PREOUTPUT_CHECK,
        "pil": ac.ENABLE_PIL_MIDDLEWARE,
        "design_state": ac.ENABLE_DESIGN_STATE_SUMMARY,
    }
    try:
        ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = True
        ac.ENABLE_EXPERIENCE_BOUNDARY = False
        ac.ENABLE_EXPERIENCE_PATCH_EXECUTION = False
        ac.ENABLE_PREOUTPUT_CHECK = False
        ac.ENABLE_PIL_MIDDLEWARE = False
        ac.ENABLE_DESIGN_STATE_SUMMARY = False
        result = {}
        for attempt in range(3):
            result = ac.chat_turn(
                message, history, state, turn_id=6, capture_stages=True
            )
            if result.get("model_status") != "failed":
                break
            print(f"retry={attempt + 1}", flush=True)
    finally:
        ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = flags["candidate"]
        ac.ENABLE_EXPERIENCE_BOUNDARY = flags["experience"]
        ac.ENABLE_EXPERIENCE_PATCH_EXECUTION = flags["patch"]
        ac.ENABLE_PREOUTPUT_CHECK = flags["preoutput"]
        ac.ENABLE_PIL_MIDDLEWARE = flags["pil"]
        ac.ENABLE_DESIGN_STATE_SUMMARY = flags["design_state"]

    reply = result.get("reply") or ""
    result_state = result.get("state") or state
    stages = result.get("stages") or {}
    conflicts = sorted(
        ac._rejected_route_topology_conflicts(reply, message, result_state)
    )
    lines = [
        "# 候选路线第 6 轮定向真实复测",
        "",
        f"日期：{datetime.now().strftime('%Y-%m-%d')}",
        "",
        "说明：复用已保存完整真实对话的前 5 轮，仅重跑关键第 6 轮。",
        "",
        f"**学生：** {message}",
        "",
        "**筑思 Agent：**",
        "",
        reply,
        "",
        "内部记录："
        f"model_status={result.get('model_status')}；"
        f"candidate_status={stages.get('candidate_commitment_status', '')}；"
        f"body_patched={bool(stages.get('candidate_commitment_body_patched'))}；"
        f"remaining_topology_conflicts={conflicts}；"
        f"student_decisions={len(result_state.get('student_decisions') or [])}。",
    ]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(
        f"status={result.get('model_status')} patched="
        f"{bool(stages.get('candidate_commitment_body_patched'))} "
        f"conflicts={conflicts} decisions="
        f"{len(result_state.get('student_decisions') or [])}",
        flush=True,
    )
    print(f"SAVED {OUT.resolve()}", flush=True)


if __name__ == "__main__":
    main()
