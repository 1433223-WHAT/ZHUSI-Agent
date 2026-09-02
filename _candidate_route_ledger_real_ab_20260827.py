"""Real-chain A/B for the experimental Candidate Route Ledger sidecar."""

from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
import re

import architect_chat as ac
from candidate_route_ledger import (
    add_route,
    apply_user_route_response,
    build_generator_route_context,
    empty_route_ledger,
)
from conversation_state import empty_state


OUT = Path(
    "../03_AI测试记录/项目日志/"
    "2026年8月27日_Candidate_Route_Ledger_最小真实AB报告.md"
)

HISTORY = [
    {
        "role": "user",
        "content": "我做一个小型社区图书馆，希望不同年龄的人愿意停留。先给一个可画骨架。",
    },
    {
        "role": "assistant",
        "content": (
            "我先提出一版中心放射的测试骨架：中央共享空间连接儿童活动、普通阅览和安静阅读。"
            "这是 AI 提出的候选，不是你的决定，可以修改或放弃。"
        ),
    },
]

CASES = (
    (
        "继续探索",
        "这个方向可以继续看看，帮我展开入口和流线，但不要当成确定方案。",
    ),
    (
        "深化候选",
        "基于刚才的中心放射方向继续深化入口和流线，这仍是候选。",
    ),
    (
        "补充场地事实",
        "基地东侧有公园，北侧有道路。先讨论场地关系，不要默认沿用刚才骨架。",
    ),
    (
        "明确拒绝",
        "不要中心放射这个方向，换一个不依赖中心空间的骨架。",
    ),
    (
        "明确确认",
        "我决定采用中心放射的空间骨架，请继续深化入口和流线。",
    ),
)


@contextmanager
def inject_route_context(context: str | None):
    original = ac._apply_candidate_commitment_boundary_policy

    def wrapped(policy: str, last_user: str, intent: str) -> str:
        base = original(policy, last_user, intent)
        if not context:
            return base
        return (base + "\n" + context).strip()

    ac._apply_candidate_commitment_boundary_policy = wrapped
    try:
        yield
    finally:
        ac._apply_candidate_commitment_boundary_policy = original


def design_labor(text: str) -> list[str]:
    dimensions = {
        "功能关系": ("功能", "邻接", "分区"),
        "空间骨架": ("骨架", "组织", "流线", "入口"),
        "体量/剖面": ("体量", "剖面", "层", "挑空"),
        "可画动作": ("画", "草图", "平面", "标出", "可画"),
    }
    return [name for name, terms in dimensions.items() if any(term in text for term in terms)]


def degradation(text: str) -> list[str]:
    hits = []
    if any(term in text for term in ("无法判断", "信息不足，无法", "不能给出建议")):
        hits.append("无法判断式退化")
    if any(term in text for term in ("Route Ledger", "生成权限", "R001", "内部规则")):
        hits.append("隐藏台账外显")
    if text.count("需要确认") + text.count("需要验证") >= 6:
        hits.append("条件句膨胀")
    return hits


def route_errors(text: str, expected_status: str) -> list[str]:
    hits = []
    if expected_status in {"proposed", "active_candidate", "suspended"}:
        patterns = (
            r"你的方案采用.{0,20}中心放射",
            r"中心放射.{0,20}(?:已经确定|作为既定|确定采用|就是当前方案)",
            r"基于(?:已经)?确定的中心放射",
        )
    elif expected_status == "rejected":
        patterns = (
            r"(?:继续|沿用|采用|保留).{0,20}中心放射",
            r"中心放射.{0,20}(?:继续深化|作为骨架|组织功能)",
        )
    else:
        patterns = (
            r"中心放射.{0,20}(?:尚未确认|仍是候选|只是候选|测试方向)",
            r"(?:尚未确认|仍是候选|只是候选).{0,20}中心放射",
        )
    for pattern in patterns:
        hits.extend(match.group(0) for match in re.finditer(pattern, text))
    return hits


def make_ledger(message: str) -> dict:
    ledger = empty_route_ledger()
    add_route(
        ledger,
        statement="采用中心放射的空间骨架",
        source="ai",
        turn_id=1,
    )
    apply_user_route_response(ledger, message, turn_id=2)
    return ledger


def run_case(message: str, ledger_enabled: bool) -> dict:
    ledger = make_ledger(message)
    context = build_generator_route_context(ledger) if ledger_enabled else None
    with inject_route_context(context):
        result = ac.chat_turn(
            message,
            deepcopy(HISTORY),
            empty_state(),
            turn_id=2,
            capture_stages=True,
        )
    reply = result.get("reply") or ""
    route = ledger["routes"][0]
    return {
        "reply": reply,
        "status": route["status"],
        "errors": route_errors(reply, route["status"]),
        "labor": design_labor(reply),
        "degradation": degradation(reply),
        "state_has_ledger": "route_ledger" in (result.get("state") or {}),
        "question_patched": bool(
            (result.get("stages") or {}).get("candidate_route_question_patched")
        ),
    }


def write_report(rows: list[dict]) -> None:
    a_errors = sum(len(row["a"]["errors"]) for row in rows)
    b_errors = sum(len(row["b"]["errors"]) for row in rows)
    a_labor = sum(len(row["a"]["labor"]) for row in rows)
    b_labor = sum(len(row["b"]["labor"]) for row in rows)
    a_degradation = sum(bool(row["a"]["degradation"]) for row in rows)
    b_degradation = sum(bool(row["b"]["degradation"]) for row in rows)
    lines = [
        "# Candidate Route Ledger 最小真实 A/B 报告",
        "",
        "日期：2026-08-27",
        "",
        "A 组：现有 Candidate Boundary。B 组：同一真实生成链，额外注入实验 Route Ledger 生成权限。",
        "正式 State、RAG、G Check、Boundary 均未修改。",
        "",
        "## 汇总",
        "",
        f"- 路线身份错误：A={a_errors}，B={b_errors}",
        f"- 设计劳动：A={a_labor}/20，B={b_labor}/20",
        f"- 退化案例：A={a_degradation}/5，B={b_degradation}/5",
        f"- 台账写入正式 State：A={any(row['a']['state_has_ledger'] for row in rows)}，"
        f"B={any(row['b']['state_has_ledger'] for row in rows)}",
        "",
        "自动指标只用于定位；最终结论需要逐案语义审阅。",
        "",
    ]
    for row in rows:
        lines.extend((
            f"## {row['title']}",
            "",
            f"用户：{row['message']}",
            "",
            f"台账期望状态：{row['b']['status']}",
            "",
            f"### A 输出（错误={row['a']['errors'] or '无'}；设计劳动={'、'.join(row['a']['labor']) or '无'}；"
            f"退化={row['a']['degradation'] or '无'}）",
            "",
            row["a"]["reply"],
            "",
            f"### B 输出（错误={row['b']['errors'] or '无'}；设计劳动={'、'.join(row['b']['labor']) or '无'}；"
            f"退化={row['b']['degradation'] or '无'}）",
            "",
            row["b"]["reply"],
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
    rows = []
    try:
        ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = True
        ac.ENABLE_EXPERIENCE_BOUNDARY = False
        ac.ENABLE_EXPERIENCE_PATCH_EXECUTION = False
        ac.ENABLE_PIL_MIDDLEWARE = False
        ac.ENABLE_DESIGN_STATE_SUMMARY = False
        for title, message in CASES:
            row = {
                "title": title,
                "message": message,
                "a": run_case(message, False),
                "b": run_case(message, True),
            }
            rows.append(row)
            write_report(rows)
    finally:
        ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = old["candidate"]
        ac.ENABLE_EXPERIENCE_BOUNDARY = old["experience"]
        ac.ENABLE_EXPERIENCE_PATCH_EXECUTION = old["patch"]
        ac.ENABLE_PIL_MIDDLEWARE = old["pil"]
        ac.ENABLE_DESIGN_STATE_SUMMARY = old["design_state"]
        write_report(rows)

    print(f"report={OUT.resolve()}")
    print(f"cases={len(rows)}")
    print(f"route_errors A={sum(len(row['a']['errors']) for row in rows)} B={sum(len(row['b']['errors']) for row in rows)}")
    print(f"design_labor A={sum(len(row['a']['labor']) for row in rows)}/20 B={sum(len(row['b']['labor']) for row in rows)}/20")
    print(f"degradation A={sum(bool(row['a']['degradation']) for row in rows)}/5 B={sum(bool(row['b']['degradation']) for row in rows)}/5")
    print(f"state_pollution B={any(row['b']['state_has_ledger'] for row in rows)}")


if __name__ == "__main__":
    main()
