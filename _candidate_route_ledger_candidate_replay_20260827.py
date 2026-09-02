"""Targeted replay for the candidate-development case invalidated by intent routing."""

from pathlib import Path

import architect_chat as ac
import _candidate_route_ledger_real_ab_20260827 as ab


OUT = Path(
    "../03_AI测试记录/项目日志/"
    "2026年8月27日_Candidate_Route_Ledger_候选深化补充复测.md"
)
MESSAGE = (
    "沿中心放射这个候选继续往下设计入口和流线。这不是修改上一段文字，"
    "也不是确认方案；请直接提供新的空间推演和可画动作。"
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
        a = ab.run_case(MESSAGE, False)
        b = ab.run_case(MESSAGE, True)
    finally:
        ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = old["candidate"]
        ac.ENABLE_EXPERIENCE_BOUNDARY = old["experience"]
        ac.ENABLE_EXPERIENCE_PATCH_EXECUTION = old["patch"]
        ac.ENABLE_PIL_MIDDLEWARE = old["pil"]
        ac.ENABLE_DESIGN_STATE_SUMMARY = old["design_state"]

    lines = [
        "# Candidate Route Ledger 候选深化补充复测",
        "",
        "日期：2026-08-27",
        "",
        f"用户：{MESSAGE}",
        "",
        f"A：status={a['status']}；错误={a['errors'] or '无'}；设计劳动={'、'.join(a['labor']) or '无'}；退化={a['degradation'] or '无'}。",
        "",
        a["reply"],
        "",
        f"B：status={b['status']}；错误={b['errors'] or '无'}；设计劳动={'、'.join(b['labor']) or '无'}；退化={b['degradation'] or '无'}。",
        "",
        b["reply"],
        "",
    ]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"report={OUT.resolve()}")
    print(f"A status={a['status']} errors={len(a['errors'])} labor={len(a['labor'])}/4 degradation={bool(a['degradation'])}")
    print(f"B status={b['status']} errors={len(b['errors'])} labor={len(b['labor'])}/4 degradation={bool(b['degradation'])}")
    print(f"state_pollution B={b['state_has_ledger']}")


if __name__ == "__main__":
    main()
