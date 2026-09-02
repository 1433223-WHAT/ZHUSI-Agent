"""Real-chain A/B for the repaired, existing Design State summary wiring."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import re

import architect_chat as ac
from conversation_state import empty_state


OUT = Path(
    "../03_AI测试记录/项目日志/"
    "2026年8月27日_Design_State_既有链路接线_真实AB验证.md"
)

CASES = (
    {
        "title": "普通弱认可",
        "message": "嗯，这个中庭听着还可以，你接着往下弄吧。",
        "expected": "candidate",
    },
    {
        "title": "引用上轮继续深化",
        "message": "基于刚才的中庭方向继续深化入口和首层流线，先看看效果。",
        "expected": "candidate",
    },
    {
        "title": "小白式含糊续接",
        "message": "这个还行，你再往下整具体点。",
        "expected": "candidate",
    },
    {
        "title": "明确确认控制组",
        "message": "行，就这么做吧，中庭就定下来，继续深化入口和剖面。",
        "expected": "confirmed",
    },
    {
        "title": "明确拒绝并换路",
        "message": "这个不太行，我不想要中庭了，换个不依赖中庭的方向。",
        "expected": "rejected",
    },
)

_CERTAINTY_RE = re.compile(
    r"你的方案(?:采用|就是)|已经确定|确定采用|中庭(?:是|作为)当前方案|"
    r"当前方案(?:采用|确定为)|就按中庭|必须采用|主入口应该"
)
_CONDITIONAL_RE = re.compile(r"候选|暂定|可以|可作为|先按|如果|待验证|仍可|可调整|可替换|未确认")
_HIDDEN_ROUTE_RE = re.compile(
    r"你(?:更|是)?(?:喜欢|倾向|希望|想选).{0,16}(?:还是|或)|"
    r"你想要.{0,16}(?:还是|或)|(?:选择|确定).{0,10}(?:中庭|线性|庭院|主街)"
)


def seeded_state() -> dict:
    state = empty_state()
    state["project"]["project_type"] = {
        "value": "社区文化中心",
        "status": "confirmed",
        "source": "student",
        "turn_id": 1,
    }
    state["project"]["goals"] = {
        "value": "空间开放，居民平时愿意进入停留",
        "status": "confirmed",
        "source": "student",
        "turn_id": 1,
    }
    state["collaboration_focus"]["design_stage"] = {
        "value": "early_concept",
        "evidence": "刚开始做方案",
        "source": "student",
        "turn_id": 1,
        "status": "confirmed",
    }
    state["issue_register"] = {
        "issue-1-1": {
            "text": "中央中庭作为公共空间组织候选",
            "origin": "ai",
            "status": "candidate",
            "proposed_turn": 1,
            "confirmed_turn": None,
            "evidence": "AI 上轮提出的测试骨架",
        }
    }
    state["framework_trail"] = [
        {
            "text": "中央中庭作为公共空间组织候选",
            "origin": "ai_suggestion",
            "turn_id": 1,
            "status": "proposed",
        }
    ]
    return state


HISTORY = [
    {"role": "user", "content": "我刚开始做社区文化中心，希望空间开放一点，你先给个起点。"},
    {
        "role": "assistant",
        "content": "可以先把中央中庭作为一个测试骨架，围绕它比较入口、公共活动和楼层联系；这只是候选，可以调整或放弃。",
    },
]


def certainty_hits(text: str, expected: str) -> list[str]:
    if expected == "confirmed":
        return []
    hits = []
    for sentence in re.split(r"[。！？!？\n]", text or ""):
        if _CONDITIONAL_RE.search(sentence):
            continue
        hits.extend(match.group(0) for match in _CERTAINTY_RE.finditer(sentence))
    return hits


def design_labor(text: str) -> tuple[int, list[str]]:
    dimensions = {
        "功能关系": ("功能", "公共", "活动", "邻接", "后勤"),
        "空间骨架": ("骨架", "组织", "入口", "流线", "空间序列"),
        "体量或剖面": ("体量", "剖面", "首层", "二层", "挑空", "高度"),
        "可画动作": ("画", "草图", "平面", "剖面", "标出", "落图"),
    }
    found = [name for name, terms in dimensions.items() if any(term in (text or "") for term in terms)]
    return len(found), found


def degradation(text: str) -> list[str]:
    flags = []
    if any(term in text for term in ("无法判断", "信息不足，无法", "不能继续", "无法给出")):
        flags.append("停止推进")
    if any(term in text for term in ("Design State Hidden Summary", "当前候选状态", "未确认决策")):
        flags.append("内部状态外显")
    if text.count("需要确认") + text.count("需要验证") + text.count("无法确定") >= 6:
        flags.append("条件膨胀")
    return flags


def state_status(state: dict) -> str:
    issue = (state.get("issue_register") or {}).get("issue-1-1") or {}
    status = issue.get("status") or "missing"
    if status == "active":
        return "confirmed"
    return status


def run_variant(case: dict, enabled: bool) -> dict:
    ac.ENABLE_DESIGN_STATE_SUMMARY = enabled
    result = ac.chat_turn(
        case["message"],
        deepcopy(HISTORY),
        seeded_state(),
        turn_id=2,
        capture_stages=True,
    )
    reply = result.get("reply") or ""
    labor_score, labor_items = design_labor(reply)
    return {
        "reply": reply,
        "state_status": state_status(result.get("state") or {}),
        "certainty": certainty_hits(reply, case["expected"]),
        "hidden_route": len(_HIDDEN_ROUTE_RE.findall(reply)),
        "labor_score": labor_score,
        "labor_items": labor_items,
        "degradation": degradation(reply),
        "summary_enabled": bool(result.get("design_state_summary_enabled")),
    }


def render(rows: list[dict]) -> str:
    candidate_rows = [row for row in rows if row["case"]["expected"] == "candidate"]
    a_certainty = sum(len(row["a"]["certainty"]) for row in candidate_rows)
    b_certainty = sum(len(row["b"]["certainty"]) for row in candidate_rows)
    a_routes = sum(row["a"]["hidden_route"] for row in rows)
    b_routes = sum(row["b"]["hidden_route"] for row in rows)
    a_labor = sum(row["a"]["labor_score"] for row in rows)
    b_labor = sum(row["b"]["labor_score"] for row in rows)
    a_degradation = sum(bool(row["a"]["degradation"]) for row in rows)
    b_degradation = sum(bool(row["b"]["degradation"]) for row in rows)
    state_errors_a = sum(row["a"]["state_status"] != row["case"]["expected"] for row in rows)
    state_errors_b = sum(row["b"]["state_status"] != row["case"]["expected"] for row in rows)

    lines = [
        "# Design State 既有链路接线真实 A/B 验证",
        "",
        "日期：2026-08-27",
        "",
        "## 范围",
        "",
        "A 保持现有真实生成链并关闭 Design State Hidden Summary；B 只开启该已有摘要。Candidate Boundary 在两组均保持当前开启状态；Experience Boundary、PIL、Experience Patch 均关闭。",
        "",
        "## 汇总",
        "",
        f"- Candidate 强确定表达：A={a_certainty}，B={b_certainty}。",
        f"- 状态转换错误：A={state_errors_a}/5，B={state_errors_b}/5。",
        f"- 隐性路线引导：A={a_routes}，B={b_routes}。",
        f"- 设计劳动：A={a_labor}/20，B={b_labor}/20。",
        f"- 退化案例：A={a_degradation}/5，B={b_degradation}/5。",
        "",
        "自动统计只用于定位，结论必须结合下方原始回答复核。",
        "",
    ]
    for row in rows:
        case = row["case"]
        lines.extend((
            f"## {case['title']}",
            "",
            f"用户：{case['message']}",
            "",
            f"预期状态：{case['expected']}",
            "",
            f"A：状态={row['a']['state_status']}；强确定={row['a']['certainty'] or '无'}；隐性引导={row['a']['hidden_route']}；设计劳动={row['a']['labor_score']}/4（{'、'.join(row['a']['labor_items']) or '无'}）；退化={row['a']['degradation'] or '无'}。",
            "",
            "### A 原始回答",
            "",
            row["a"]["reply"],
            "",
            f"B：状态={row['b']['state_status']}；强确定={row['b']['certainty'] or '无'}；隐性引导={row['b']['hidden_route']}；设计劳动={row['b']['labor_score']}/4（{'、'.join(row['b']['labor_items']) or '无'}）；退化={row['b']['degradation'] or '无'}。",
            "",
            "### B 原始回答",
            "",
            row["b"]["reply"],
            "",
        ))
    return "\n".join(lines)


def main() -> None:
    old = {
        "design_state": ac.ENABLE_DESIGN_STATE_SUMMARY,
        "candidate": ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY,
        "experience": ac.ENABLE_EXPERIENCE_BOUNDARY,
        "patch": ac.ENABLE_EXPERIENCE_PATCH_EXECUTION,
        "pil": ac.ENABLE_PIL_MIDDLEWARE,
    }
    rows = []
    try:
        ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = True
        ac.ENABLE_EXPERIENCE_BOUNDARY = False
        ac.ENABLE_EXPERIENCE_PATCH_EXECUTION = False
        ac.ENABLE_PIL_MIDDLEWARE = False
        for case in CASES:
            print(f"running A: {case['title']}", flush=True)
            a = run_variant(case, False)
            print(f"running B: {case['title']}", flush=True)
            b = run_variant(case, True)
            rows.append({"case": case, "a": a, "b": b})
    finally:
        ac.ENABLE_DESIGN_STATE_SUMMARY = old["design_state"]
        ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = old["candidate"]
        ac.ENABLE_EXPERIENCE_BOUNDARY = old["experience"]
        ac.ENABLE_EXPERIENCE_PATCH_EXECUTION = old["patch"]
        ac.ENABLE_PIL_MIDDLEWARE = old["pil"]

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(render(rows), encoding="utf-8")
    print(f"report={OUT.resolve()}")


if __name__ == "__main__":
    main()
