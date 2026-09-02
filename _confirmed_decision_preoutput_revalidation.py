"""Single-case real-chain revalidation for confirmed-decision preservation."""

from pathlib import Path

import architect_chat as ac
from conversation_state import empty_state


OUT = Path(
    "../03_AI测试记录/项目日志/"
    "2026年8月24日_已确认设计决定_隐藏检查回归验证报告.md"
)
PROMPT = "我已经决定采用中央中庭组织方式，请继续深化入口和流线。"


def main() -> None:
    old = {
        "candidate": ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY,
        "experience": ac.ENABLE_EXPERIENCE_BOUNDARY,
        "patch": ac.ENABLE_EXPERIENCE_PATCH_EXECUTION,
        "pil": ac.ENABLE_PIL_MIDDLEWARE,
        "design_state": ac.ENABLE_DESIGN_STATE_SUMMARY,
        "preoutput": ac.ENABLE_PREOUTPUT_CHECK,
    }
    try:
        ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = True
        ac.ENABLE_EXPERIENCE_BOUNDARY = False
        ac.ENABLE_EXPERIENCE_PATCH_EXECUTION = False
        ac.ENABLE_PIL_MIDDLEWARE = False
        ac.ENABLE_DESIGN_STATE_SUMMARY = False
        ac.ENABLE_PREOUTPUT_CHECK = True
        result = ac.chat_turn(PROMPT, [], empty_state(), turn_id=1, capture_stages=True)
    finally:
        ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = old["candidate"]
        ac.ENABLE_EXPERIENCE_BOUNDARY = old["experience"]
        ac.ENABLE_EXPERIENCE_PATCH_EXECUTION = old["patch"]
        ac.ENABLE_PIL_MIDDLEWARE = old["pil"]
        ac.ENABLE_DESIGN_STATE_SUMMARY = old["design_state"]
        ac.ENABLE_PREOUTPUT_CHECK = old["preoutput"]

    stages = result.get("stages") or {}
    raw = stages.get("raw_draft") or ""
    checked = stages.get("checked_draft") or ""
    final = stages.get("final_after_boundary") or result.get("reply") or ""
    leaked = any(term in final for term in (
        "修订后的完整方案", "内部检查结果", "检查结果如下",
    ))
    demoted = any(term in final for term in (
        "非你的决定", "不是你的决定", "尚未确认", "还未确认", "未确认采用", "不是定案",
    ))
    decision_preserved = any(term in final for term in (
        "已经确认", "已确认", "你已经决定", "采用中央中庭", "中央中庭作为组织",
    ))
    design_progress = all(term in final for term in ("入口", "流线"))

    lines = [
        "# 已确认设计决定隐藏检查回归验证报告",
        "",
        "日期：2026-08-24",
        "",
        f"用户输入：{PROMPT}",
        "",
        "## 结果",
        "",
        f"- 隐藏检查标题外显：{'是' if leaked else '否'}。",
        f"- 已确认决定被降级：{'是' if demoted else '否'}。",
        f"- 中庭决定得到保留：{'是' if decision_preserved else '否'}。",
        f"- 入口与流线继续深化：{'是' if design_progress else '否'}。",
        f"- Hidden Check 改写发生：{'是' if checked != raw else '否'}。",
        "",
        "## Generator 原稿",
        "",
        raw,
        "",
        "## Hidden Check 后",
        "",
        checked,
        "",
        "## 最终回答",
        "",
        final,
    ]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"report={OUT.resolve()}")
    print(f"leaked={leaked}")
    print(f"demoted={demoted}")
    print(f"decision_preserved={decision_preserved}")
    print(f"design_progress={design_progress}")


if __name__ == "__main__":
    main()
