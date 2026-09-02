"""Resume the saved beginner-student live session without re-calling prior model turns."""

from __future__ import annotations

import json
from pathlib import Path
import re
import sys

import architect_chat as ac
from conversation_state import (
    answer_pending_question,
    apply_semantic_events,
    empty_state,
    record_ai_question,
    record_framework,
    record_issue,
    split_meta_feedback,
    update_state,
)


SOURCE = Path("../03_AI测试记录/项目日志/2026年8月25日_初学建筑学生_第二轮完整真实对话观察记录.md")
OUT = Path("../03_AI测试记录/项目日志/2026年8月25日_初学建筑学生_第二轮真实对话第10轮起续跑记录.md")


def _parse_rows() -> list[dict]:
    text = SOURCE.read_text(encoding="utf-8")
    pattern = re.compile(
        r"## 第 (?P<turn>\d+) 轮\n\n"
        r"\*\*学生：\*\* (?P<user>.*?)\n\n"
        r"\*\*筑思 Agent：\*\*\n\n(?P<reply>.*?)\n\n"
        r"内部记录：intent=(?P<intent>.*?)；candidate_status=(?P<candidate>.*?)；"
        r"body_patched=(?P<body>True|False)；question_patched=(?P<question>True|False)；"
        r"student_decisions=(?P<decisions>\d+)。",
        re.DOTALL,
    )
    return [
        {
            "turn": int(match.group("turn")),
            "user": match.group("user").strip(),
            "reply": match.group("reply").strip(),
            "intent": match.group("intent").strip(),
            "candidate_status": match.group("candidate").strip(),
            "body_patched": match.group("body") == "True",
            "question_patched": match.group("question") == "True",
            "student_decisions": int(match.group("decisions")),
        }
        for match in pattern.finditer(text)
    ]


def _replay_state(rows: list[dict]) -> dict:
    state = empty_state()
    for row in rows:
        message = row["user"]
        turn_id = row["turn"]
        _, design_message = split_meta_feedback(message)
        design_text = design_message or message
        intent = ac.classify_intent(design_text)

        apply_semantic_events(state, design_text, turn_id)
        updated = update_state(state, design_text, turn_id)
        updated = ac.update_focus(updated, design_text, turn_id)
        ac._record_numeric_correction(updated, design_text, turn_id)
        ac._apply_state_revision(updated, design_text, turn_id)
        ac._apply_topic_return(updated, design_text, turn_id)
        ac._apply_weak_ack(updated, design_text, turn_id)
        ac._apply_issue_confirmation(updated, design_text, turn_id)

        if intent == "general_architecture_chat" and not re.search(
            r"面向|服务于|使用者|场地|基地|平方米|平米|㎡|功能(?:是|包括)|目标(?:是|为)|限制(?:是|为)",
            design_text,
        ):
            updated = answer_pending_question(updated, design_text, turn_id)

        if "本轮建筑对话调用失败" not in row["reply"]:
            proposal = ac._detect_ai_proposal(row["reply"])
            if proposal:
                record_issue(updated, proposal, "ai", turn_id, status="proposed")
                record_framework(updated, proposal, "ai_suggestion", turn_id, status="proposed")
        question_dimension = ac._question_dimension(row["reply"])
        if question_dimension:
            updated = record_ai_question(
                updated,
                row["reply"].strip().splitlines()[-1],
                question_dimension,
                turn_id,
            )

        actual = len(updated.get("student_decisions") or [])
        if actual != row["student_decisions"]:
            raise RuntimeError(
                f"turn {turn_id} state mismatch: recorded={row['student_decisions']} replayed={actual}"
            )
        state = updated
    return state


def _write_continuation(rows: list[dict]) -> None:
    lines = [
        "# 初学建筑学生第二轮真实对话续跑记录",
        "",
        "日期：2026-08-25",
        "",
        "说明：从已保存的第 1-9 轮全文重建历史与确定性状态，并校验 student_decisions 后，自第 10 轮恢复真实生成。",
        "",
    ]
    for row in rows:
        lines.extend((
            f"## 第 {row['turn']} 轮",
            "",
            f"**学生：** {row['user']}",
            "",
            "**筑思 Agent：**",
            "",
            row["reply"],
            "",
            f"内部记录：intent={row['intent']}；candidate_status={row['candidate_status']}；body_patched={row['body_patched']}；question_patched={row['question_patched']}；student_decisions={row['student_decisions']}。",
            "",
            "---",
            "",
        ))
    OUT.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    prior_rows = _parse_rows()
    if not prior_rows or prior_rows[-1]["turn"] != 9:
        raise RuntimeError("expected saved turns 1-9")
    state = _replay_state(prior_rows)
    history = []
    for row in prior_rows:
        history.extend((
            {"role": "user", "content": row["user"]},
            {"role": "assistant", "content": row["reply"]},
        ))

    continuation: list[dict] = []
    print(f"READY_RESUME decisions={len(state.get('student_decisions') or [])}", flush=True)
    for raw in sys.stdin:
        message = raw.strip()
        if not message:
            continue
        if message == "/quit":
            break
        turn = 10 + len(continuation)
        result = ac.chat_turn(message, history, state, turn_id=turn, capture_stages=True)
        reply = result.get("reply") or ""
        stages = result.get("stages") or {}
        state = result.get("state") or state
        row = {
            "turn": turn,
            "user": message,
            "reply": reply,
            "intent": result.get("intent", ""),
            "candidate_status": stages.get("candidate_commitment_status", ""),
            "body_patched": bool(stages.get("candidate_commitment_body_patched")),
            "question_patched": bool(stages.get("candidate_route_question_patched")),
            "student_decisions": len(state.get("student_decisions") or []),
        }
        continuation.append(row)
        history.extend((
            {"role": "user", "content": message},
            {"role": "assistant", "content": reply},
        ))
        _write_continuation(continuation)
        print("REPLY_BEGIN", flush=True)
        print(reply, flush=True)
        print("REPLY_END", flush=True)
        print("META " + json.dumps({
            "turn": turn,
            "intent": row["intent"],
            "candidate_status": row["candidate_status"],
            "student_decisions": row["student_decisions"],
        }, ensure_ascii=False), flush=True)
    _write_continuation(continuation)
    print(f"SAVED {OUT.resolve()}", flush=True)


if __name__ == "__main__":
    main()
