"""Interactive real-chain session used for a beginner architecture-student review."""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import sys

import architect_chat as ac
from conversation_state import empty_state


RUN_DATE = datetime.now().strftime("%Y-%m-%d")
RUN_DATE_CN = f"{datetime.now().year}年{datetime.now().month}月{datetime.now().day}日"
OUT = Path(
    "../03_AI测试记录/项目日志/"
    f"{RUN_DATE_CN}_普通初学者_自然设计流程完整模拟测试.md"
)


def _write_transcript(rows: list[dict]) -> None:
    lines = [
        "# 普通初学者自然设计流程完整模拟测试记录",
        "",
        f"日期：{RUN_DATE}",
        "",
        "实验设置：真实筑思生成链；Candidate Commitment Boundary 与实验版 Experience Patch 开启；Experience Boundary、PIL、Design State 关闭。",
        "",
        "项目：约 3000㎡ 社区活动中心。普通初学者先以模糊任务进入对话，随后自然补充北侧社区路、东侧绿地等条件；不预先使用边界测试术语。以上均为本次测试构造的课程设计条件，不是外部真实项目资料。",
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
    state = empty_state()
    history: list[dict] = []
    rows: list[dict] = []
    try:
        ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = True
        ac.ENABLE_EXPERIENCE_BOUNDARY = False
        # Experiment-only: production default in architect_chat.py remains off.
        ac.ENABLE_EXPERIENCE_PATCH_EXECUTION = True
        ac.ENABLE_PIL_MIDDLEWARE = False
        ac.ENABLE_DESIGN_STATE_SUMMARY = False
        print("READY", flush=True)
        for raw in sys.stdin:
            message = raw.strip()
            if not message:
                continue
            if message == "/quit":
                break
            turn = len(rows) + 1
            result = ac.chat_turn(
                message,
                history,
                state,
                turn_id=turn,
                capture_stages=True,
            )
            reply = result.get("reply") or ""
            stages = result.get("stages") or {}
            rows.append({
                "turn": turn,
                "user": message,
                "reply": reply,
                "intent": result.get("intent", ""),
                "candidate_status": stages.get("candidate_commitment_status", ""),
                "body_patched": bool(stages.get("candidate_commitment_body_patched")),
                "question_patched": bool(stages.get("candidate_route_question_patched")),
                "student_decisions": len((result.get("state") or {}).get("student_decisions") or []),
            })
            history.extend((
                {"role": "user", "content": message},
                {"role": "assistant", "content": reply},
            ))
            state = result.get("state") or state
            _write_transcript(rows)
            print("REPLY_BEGIN", flush=True)
            print(reply, flush=True)
            print("REPLY_END", flush=True)
            print(
                "META "
                + json.dumps(
                    {
                        "turn": turn,
                        "intent": result.get("intent", ""),
                        "candidate_status": stages.get("candidate_commitment_status", ""),
                        "student_decisions": len(state.get("student_decisions") or []),
                    },
                    ensure_ascii=False,
                ),
                flush=True,
            )
    finally:
        ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = old["candidate"]
        ac.ENABLE_EXPERIENCE_BOUNDARY = old["experience"]
        ac.ENABLE_EXPERIENCE_PATCH_EXECUTION = old["patch"]
        ac.ENABLE_PIL_MIDDLEWARE = old["pil"]
        ac.ENABLE_DESIGN_STATE_SUMMARY = old["design_state"]
        _write_transcript(rows)
        print(f"SAVED {OUT.resolve()} {datetime.now().isoformat(timespec='seconds')}", flush=True)


if __name__ == "__main__":
    main()
