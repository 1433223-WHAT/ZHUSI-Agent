"""Real-chain regression for rejected route topology and decision ownership."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import architect_chat as ac
from conversation_state import empty_state


MESSAGES = [
    "老师，我刚开始学建筑，现在要做一个大概三千平的社区活动中心，我脑子里还挺乱的，入口和里面怎么组织都没想好。你先帮我看看整体可以怎么开始？",
    "有场地，北边是社区路，东边是绿地，西边挨着住宅，南边我也不太清楚。老师只说会有活动室、阅览、小剧场和办公室，其他我还没理。你就按这些先带我往下走吧。",
    "完整功能我一时拿不到，先别卡在这儿。北边做入口听着好像也行，你先按这个看看，把首层和二层大概怎么放说清楚一点。",
    "我看着觉得大厅太占地方了，我不想用大厅当心脏。能不能换一种没那么中心化的？功能先还按这几个，你直接帮我改一版吧。",
    "线性这个我又觉得有点像学校走廊，也不是很喜欢。有没有不靠一个大厅、也不靠一条街的？我就是想让几个活动地方各自有点独立，但也别散得找不到人。",
    "可是你这个不还是让大家围着中间一个院子吗？我刚才说了不想靠一个中心。你别再换个名字绕回来，按我说的‘各自独立但别太散’重新想一个，直接给我关系，不用再让我选类型。",
]

OUT = Path(
    "../03_AI测试记录/项目日志/"
    f"{datetime.now().year}年{datetime.now().month}月{datetime.now().day}日_"
    f"Generator拒绝拓扑约束修复后B组真实复测_{datetime.now().strftime('%H%M%S')}.md"
)


def main() -> None:
    old_candidate = ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY
    old_experience = ac.ENABLE_EXPERIENCE_BOUNDARY
    old_patch = ac.ENABLE_EXPERIENCE_PATCH_EXECUTION
    old_preoutput = ac.ENABLE_PREOUTPUT_CHECK
    old_pil = ac.ENABLE_PIL_MIDDLEWARE
    old_design_state = ac.ENABLE_DESIGN_STATE_SUMMARY
    state = empty_state()
    history: list[dict] = []
    rows: list[dict] = []
    try:
        ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = True
        ac.ENABLE_EXPERIENCE_BOUNDARY = False
        ac.ENABLE_EXPERIENCE_PATCH_EXECUTION = False
        ac.ENABLE_PREOUTPUT_CHECK = False
        ac.ENABLE_PIL_MIDDLEWARE = False
        ac.ENABLE_DESIGN_STATE_SUMMARY = False
        for turn, message in enumerate(MESSAGES, start=1):
            result = {}
            for attempt in range(3):
                result = ac.chat_turn(
                    message,
                    history,
                    state,
                    turn_id=turn,
                    capture_stages=True,
                )
                if result.get("model_status") != "failed":
                    break
                print(f"turn={turn} retry={attempt + 1}", flush=True)
            reply = result.get("reply") or ""
            stages = result.get("stages") or {}
            raw_draft = stages.get("raw_draft") or ""
            state = result.get("state") or state
            rows.append({
                "turn": turn,
                "user": message,
                "reply": reply,
                "raw_draft": raw_draft,
                "raw_topology_conflicts": sorted(
                    ac._rejected_route_topology_conflicts(raw_draft, message, state)
                ),
                "candidate_status": stages.get("candidate_commitment_status", ""),
                "body_patched": bool(stages.get("candidate_commitment_body_patched")),
                "question_patched": bool(stages.get("candidate_route_question_patched")),
                "topology_conflicts_before": stages.get(
                    "topology_conflicts_before", []
                ),
                "topology_rewrite_applied": bool(
                    stages.get("topology_rewrite_applied")
                ),
                "topology_conflicts_after": stages.get(
                    "topology_conflicts_after", []
                ),
                "topology_fallback_used": bool(
                    stages.get("topology_fallback_used")
                ),
                "remaining_topology_conflicts": sorted(
                    ac._rejected_route_topology_conflicts(reply, message, state)
                ),
                "student_decisions": len(state.get("student_decisions") or []),
            })
            history.extend((
                {"role": "user", "content": message},
                {"role": "assistant", "content": reply},
            ))
            print(
                f"turn={turn} status={rows[-1]['candidate_status']} "
                f"patched={rows[-1]['body_patched']} "
                f"conflicts={rows[-1]['remaining_topology_conflicts']} "
                f"decisions={rows[-1]['student_decisions']}",
                flush=True,
            )
    finally:
        ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = old_candidate
        ac.ENABLE_EXPERIENCE_BOUNDARY = old_experience
        ac.ENABLE_EXPERIENCE_PATCH_EXECUTION = old_patch
        ac.ENABLE_PREOUTPUT_CHECK = old_preoutput
        ac.ENABLE_PIL_MIDDLEWARE = old_pil
        ac.ENABLE_DESIGN_STATE_SUMMARY = old_design_state

    lines = [
        "# Generator 拒绝拓扑约束修复后 B 组真实复测",
        "",
        f"日期：{datetime.now().strftime('%Y-%m-%d')}",
        "",
        "设置：真实筑思生成链；只开启 Candidate Commitment Boundary；"
        "Experience Patch、通用 Preoutput Check 与其他实验层关闭，以隔离本次变量。",
        "",
    ]
    for row in rows:
        lines.extend((
            f"## 第 {row['turn']} 轮",
            "",
            f"**学生：** {row['user']}",
            "",
            "**Generator 原始草稿：**",
            "",
            row["raw_draft"],
            "",
            "**筑思 Agent：**",
            "",
            row["reply"],
            "",
            "内部记录："
            f"candidate_status={row['candidate_status']}；"
            f"raw_topology_conflicts={row['raw_topology_conflicts']}；"
            f"body_patched={row['body_patched']}；"
            f"question_patched={row['question_patched']}；"
            f"topology_conflicts_before={row['topology_conflicts_before']}；"
            f"topology_rewrite_applied={row['topology_rewrite_applied']}；"
            f"topology_conflicts_after={row['topology_conflicts_after']}；"
            f"topology_fallback_used={row['topology_fallback_used']}；"
            f"remaining_topology_conflicts={row['remaining_topology_conflicts']}；"
            f"student_decisions={row['student_decisions']}。",
            "",
            "---",
            "",
        ))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"SAVED {OUT.resolve()}", flush=True)


if __name__ == "__main__":
    main()
