"""Small real-chain multi-turn observation for Experience Patch."""

from __future__ import annotations

from pathlib import Path
import re

import architect_chat as ac
from conversation_state import empty_state


OUT = Path(
    "../03_AI测试记录/项目日志/"
    "2026年8月24日_Experience_Patch_多轮真实观察报告.md"
)

CONVERSATIONS = [
    {
        "title": "社区中心入口关系",
        "turns": [
            "基地北侧临城市道路，南侧是住宅。先帮我推一版入口和公共空间组织骨架。",
            "北侧入口这个方向听起来可以，继续深化看看，但我还没有决定。",
            "我不想把北侧设为主入口了。请收回这个方向，改为比较东侧和西侧入口。",
        ],
        "strong_patterns": [
            r"道路.{0,25}(?:决定|意味着).{0,20}(?:入口|人流)",
            r"北侧.{0,24}(?:主入口|主要入口).{0,20}(?:放|设|承担|确定)",
            r"南侧.{0,24}(?:安静|缓冲).{0,16}(?:应该|必须|就是|作为)",
        ],
        "rejected_patterns": [
            r"(?:主入口|主要入口).{0,12}(?:放|设|位于|安排)(?:在|于)?北侧",
            r"北侧.{0,12}(?:作为|承担|设置).{0,8}(?:主入口|主要入口)",
        ],
        "labor_terms": ["入口", "公共空间", "流线", "功能", "体量", "画"],
    },
    {
        "title": "幼儿园功能关系",
        "turns": [
            "我做一个6班幼儿园，请推活动室、寝室和室外活动场地的关系，同时方便老师照看。",
            "活动室居中的组织听起来不错，可以继续深化看看，但我还没有确定。",
            "我不想让寝室必须通过活动室到室外，也不确定每班都要独立小院。请收回这些前提，换一种关系继续推。",
        ],
        "strong_patterns": [
            r"活动室.{0,30}(?:必须|应该|最好|要求最高|是(?:照看)?枢纽)",
            r"寝室.{0,24}(?:(?:不能|不应|必须).{0,16}(?:连接|直通|通过|靠近|远离|面向|开向|设置|布置)|不直接(?:对|连|通))",
            r"(?:每班|每个班).{0,24}(?:必须|应该|是一个独立单元|独立小院|独立场地)",
            r"班级专属场地.{0,18}(?:紧贴|直接连接|直通).{0,12}活动室",
        ],
        "rejected_patterns": [
            r"寝室.{0,18}(?:必须|只能).{0,12}通过活动室",
            r"(?:每班|每个班).{0,18}(?:必须|固定).{0,12}(?:独立小院|独立场地)",
        ],
        "labor_terms": ["活动室", "寝室", "室外", "关系", "流线", "画"],
    },
]

CONDITIONAL_RE = re.compile(r"如果|可以|候选|需要结合|需结合|取决于|待验证|可能|尚未|未确定")
RETRACTION_RE = re.compile(r"收回|没有确认|未确认|不必须|不强制|不要求|不再|不想|拒绝|不是前提|已否定|撤销")


def _strong_hits(text: str, patterns: list[str]) -> list[str]:
    hits = []
    for pattern in patterns:
        for sentence in re.findall(r"[^。！？\n]+(?:[。！？]|$)", text or ""):
            if (
                re.search(pattern, sentence)
                and not CONDITIONAL_RE.search(sentence)
                and not RETRACTION_RE.search(sentence)
            ):
                hits.append(sentence.strip())
                break
    return hits


def _rejected_hits(text: str, patterns: list[str]) -> list[str]:
    hits = []
    for pattern in patterns:
        for sentence in re.findall(r"[^。！？\n]+(?:[。！？]|$)", text or ""):
            if re.search(pattern, sentence) and not RETRACTION_RE.search(sentence):
                hits.append(pattern)
                break
    return hits


def _labor(text: str, terms: list[str]) -> int:
    return sum(term in (text or "") for term in terms)


def _degradation(text: str) -> list[str]:
    result = []
    if any(term in (text or "") for term in ("无法判断", "信息不足", "不能给出建议")):
        result.append("无法判断式退化")
    if any(term in (text or "") for term in ("内部检查结果", "project_factification", "missing_condition")):
        result.append("内部检查外显")
    condition_count = sum((text or "").count(term) for term in ("需要确认", "需要验证", "需要结合", "取决于"))
    if condition_count >= 6:
        result.append("条件句膨胀")
    return result


def _run_conversation(conversation: dict, patch_enabled: bool) -> list[dict]:
    history = []
    state = empty_state()
    rows = []
    for turn_id, message in enumerate(conversation["turns"], start=1):
        result = ac.chat_turn(
            message,
            history,
            state,
            turn_id=turn_id,
            capture_stages=True,
        )
        reply = result.get("reply") or ""
        stages = result.get("stages") or {}
        rows.append({
            "turn": turn_id,
            "user": message,
            "reply": reply,
            "raw": stages.get("raw_draft") or reply,
            "checked": stages.get("checked_draft") or reply,
            "strong_hits": _strong_hits(reply, conversation["strong_patterns"]),
            "rejected_hits": (
                _rejected_hits(reply, conversation["rejected_patterns"])
                if turn_id == len(conversation["turns"])
                else []
            ),
            "labor": _labor(reply, conversation["labor_terms"]),
            "degradation": _degradation(reply),
            "patch_changed": bool(patch_enabled and stages.get("checked_draft") != stages.get("raw_draft")),
        })
        history.extend([
            {"role": "user", "content": message},
            {"role": "assistant", "content": reply},
        ])
        state = result.get("state") or state
    return rows


def _run_group(enabled: bool) -> dict[str, list[dict]]:
    old = {
        "pre": ac.ENABLE_PREOUTPUT_CHECK,
        "patch": ac.ENABLE_EXPERIENCE_PATCH_EXECUTION,
        "experience": ac.ENABLE_EXPERIENCE_BOUNDARY,
        "candidate": ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY,
        "pil": ac.ENABLE_PIL_MIDDLEWARE,
        "design_state": ac.ENABLE_DESIGN_STATE_SUMMARY,
    }
    try:
        ac.ENABLE_PREOUTPUT_CHECK = True
        ac.ENABLE_EXPERIENCE_PATCH_EXECUTION = enabled
        ac.ENABLE_EXPERIENCE_BOUNDARY = False
        ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = False
        ac.ENABLE_PIL_MIDDLEWARE = False
        ac.ENABLE_DESIGN_STATE_SUMMARY = False
        return {
            conversation["title"]: _run_conversation(conversation, enabled)
            for conversation in CONVERSATIONS
        }
    finally:
        ac.ENABLE_PREOUTPUT_CHECK = old["pre"]
        ac.ENABLE_EXPERIENCE_PATCH_EXECUTION = old["patch"]
        ac.ENABLE_EXPERIENCE_BOUNDARY = old["experience"]
        ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = old["candidate"]
        ac.ENABLE_PIL_MIDDLEWARE = old["pil"]
        ac.ENABLE_DESIGN_STATE_SUMMARY = old["design_state"]


def _totals(group: dict[str, list[dict]]) -> dict:
    rows = [row for conversation in group.values() for row in conversation]
    return {
        "strong": sum(len(row["strong_hits"]) for row in rows),
        "rejected": sum(len(row["rejected_hits"]) for row in rows),
        "labor": sum(row["labor"] for row in rows),
        "degradation": sum(bool(row["degradation"]) for row in rows),
        "patch_changed": sum(row["patch_changed"] for row in rows),
    }


def _write_report(a_group: dict, b_group: dict) -> None:
    a = _totals(a_group)
    b = _totals(b_group)
    if b["strong"] < a["strong"] and b["labor"] >= a["labor"] and b["degradation"] <= a["degradation"]:
        conclusion = "支持：多轮中强经验断言下降，设计劳动保持，退化未增加。"
    elif b["labor"] >= a["labor"] and b["degradation"] <= a["degradation"]:
        conclusion = "部分支持：设计劳动和自然度保持，但主要错误下降证据不足。"
    else:
        conclusion = "不支持：出现设计劳动下降或退化。"
    lines = [
        "# Experience Patch 多轮真实观察报告",
        "",
        "## 设置",
        "",
        "A 为当前 Agent；B 只开启 Experience Patch。Experience Boundary、Candidate Boundary、PIL、Design State 均关闭。每组包含首次生成、轻度认可未确认、明确否定三个连续轮次。",
        "",
        "## 汇总",
        "",
        "|指标|A|B|",
        "|-|-:|-:|",
        f"|强经验断言|{a['strong']}|{b['strong']}|",
        f"|否定后旧路线复发|{a['rejected']}|{b['rejected']}|",
        f"|设计劳动|{a['labor']}/36|{b['labor']}/36|",
        f"|退化轮次|{a['degradation']}/6|{b['degradation']}/6|",
        f"|B 实际发生局部补丁|—|{b['patch_changed']}/6|",
        "",
        f"结论：{conclusion}",
        "",
    ]
    for conversation in CONVERSATIONS:
        title = conversation["title"]
        lines.extend([f"## {title}", ""])
        for label, group in (("A", a_group), ("B", b_group)):
            lines.extend([f"### {label} 组", ""])
            for row in group[title]:
                lines.extend([
                    f"#### Turn {row['turn']}",
                    "",
                    f"用户：{row['user']}",
                    "",
                    f"强经验断言：{len(row['strong_hits'])}；否定路线复发：{len(row['rejected_hits'])}；设计劳动：{row['labor']}/6；退化：{('、'.join(row['degradation']) if row['degradation'] else '无')}。",
                    "",
                    f"局部补丁实际改写：{'是' if row['patch_changed'] else '否'}。",
                    "",
                    "回答：",
                    "",
                    row["reply"],
                    "",
                ])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    a_group = _run_group(False)
    b_group = _run_group(True)
    _write_report(a_group, b_group)
    print(f"report={OUT.resolve()}")
    print(f"A={_totals(a_group)}")
    print(f"B={_totals(b_group)}")


if __name__ == "__main__":
    main()
