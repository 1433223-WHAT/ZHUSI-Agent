"""Targeted real-chain replay after the second route-question repair."""

from __future__ import annotations

from pathlib import Path

import architect_chat as ac
from conversation_state import empty_state
import _question_route_guidance_live_simulation_20260827 as sim


OUT = Path(
    "../03_AI测试记录/项目日志/"
    "2026年8月27日_提问式隐性路线修复_二次真实复测.md"
)

PROMPTS = (
    "我刚学建筑设计，做一个小型开放图书馆。目标只是让不同年龄的人愿意停留。你像导师一样推进，但不要替我决定，也不要先给我一组空间类别让我选。",
    "可以直接给一版能画的功能关系和空间骨架，不要问我核心空间角色是什么，也不要问我只能选共享大空间还是独立小空间。",
    "基地北侧有道路，东侧有绿地。入口和室外联系还没有定，请推进，但不要用问题偷偷预设路线。",
    "请检查你刚才有没有让我在你发明的分类中拍板；我没有确认任何入口方向。继续给一个不依赖选边的可画动作。",
)


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
        rows = sim.run_dialogue("二次真实复测", PROMPTS)
        sim.OUT = OUT
        sim.write_report(rows)
    finally:
        ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = old["candidate"]
        ac.ENABLE_EXPERIENCE_BOUNDARY = old["experience"]
        ac.ENABLE_EXPERIENCE_PATCH_EXECUTION = old["patch"]
        ac.ENABLE_PIL_MIDDLEWARE = old["pil"]
        ac.ENABLE_DESIGN_STATE_SUMMARY = old["design_state"]

    print(f"report={OUT.resolve()}")
    print(f"turns={len(rows)}")
    print(f"question_patched={sum(row['question_patched'] for row in rows)}")
    print(f"unowned_route_questions={sum(len(row['unowned_questions']) for row in rows)}")
    print(f"confirmed_status_turns={sum(row['status'] == 'confirmed' for row in rows)}")
    print(f"design_labor={sum(len(row['labor']) for row in rows)}/{len(rows) * 4}")
    print(f"degraded_turns={sum(bool(row['degradation']) for row in rows)}/{len(rows)}")


if __name__ == "__main__":
    main()
