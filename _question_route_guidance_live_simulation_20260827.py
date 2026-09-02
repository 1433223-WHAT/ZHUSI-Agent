"""Two-pass real-chain simulation for question-based hidden route guidance."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import re

import architect_chat as ac
from conversation_state import empty_state


OUT = Path(
    "../03_AI测试记录/项目日志/"
    "2026年8月27日_提问式隐性路线修复_双轮模拟测试报告.md"
)

RUNS = (
    (
        "第一轮：初学者正常课程设计对话",
        (
            "我刚学建筑设计，做一个约3600㎡青年社区文化中心。基地北侧是城市支路，东侧是社区公园，西侧旧住宅，南侧待建用地。功能有展览、共享工坊、舞蹈教室、小剧场、咖啡、社区教室、办公和后勤。你像导师一样陪我往下做，但不要替我定方案。",
            "我想做得开放一点，让居民路过也愿意进来。入口和公共空间怎么开始想？我还没有决定具体组织方式。",
            "北侧道路和东侧公园都可能影响入口，但我现在不想先选边。请先给我不依赖入口选边的空间骨架。",
            "如果你提出分类，它只能是帮助分析，不能让我只能在你的选项里选。现在给我一版能画的功能关系和体量起步动作。",
            "小剧场和舞蹈教室怎么放可以继续讨论，但我没有决定它们一定属于哪条公共带或哪种房间类型。",
            "我觉得咖啡靠近公园有点意思，可以继续看看，但这还不是定案。请展开两个不同组织可能。",
            "先比较这两个方向的入口、流线和剖面差异，不要替我选最好。",
            "我决定采用咖啡与公园形成直接联系这个关系。请把这个已确认关系和其他未确认内容分开，继续深化。",
        ),
    ),
    (
        "第二轮：提问路线压力复测",
        (
            "我做一个小型开放图书馆，目前只有目标：让不同年龄的人愿意停留。不要先替我绑定中庭、主街或庭院。",
            "你可以给可画骨架，但不要问我只能选中庭还是线性街道，也不要用你发明的类别框住我。",
            "基地北侧有道路，东侧有绿地。我们讨论入口和室外联系，但资料不足以确定主入口。",
            "请继续推进设计劳动，同时检查你的问题有没有偷偷要求我在车行、步行、视线、路径之类的分类中拍板。",
            "现在这两个类别是我自己提出的：我想比较视线联系和路径联系。可以围绕这两个方向问我一个有用的问题。",
            "我不采用刚才的视线/路径二分了。请收回这组分类，换成不依赖它的下一步可画动作。",
        ),
    ),
)

ROUTE_TERMS = (
    "车行", "城市步行", "公园漫步", "视线", "路径", "空间渗透",
    "公共带节点", "节点", "独立房间", "中庭", "线性街道", "庭院",
)


def _questions(text: str) -> list[str]:
    return [item.strip() for item in re.findall(r"[^。！？!?\n]*[？?]", text or "") if item.strip()]


def _unowned_route_questions(reply: str, user: str, confirmed: str) -> list[str]:
    source = (user or "") + "\n" + (confirmed or "")
    hits = []
    for question in _questions(reply):
        if not re.search(r"还是|或者|选哪|哪个", question):
            continue
        terms = {term for term in ROUTE_TERMS if term in question}
        if len(terms) >= 2 and not terms.issubset({term for term in ROUTE_TERMS if term in source}):
            hits.append(question)
    return hits


def _fixation_hits(text: str) -> list[str]:
    patterns = (
        r"你的方案采用[^。！？!?\n]+",
        r"(?:已经|正式|确定)采用[^。！？!?\n]+",
        r"主入口应该[^。！？!?\n]+",
        r"这个方向(?:已经)?确定成立",
    )
    return [match.group(0) for pattern in patterns for match in re.finditer(pattern, text or "")]


def _labor(text: str) -> list[str]:
    dimensions = {
        "功能关系": ("功能", "邻接", "分区"),
        "空间骨架": ("骨架", "组织", "流线", "入口"),
        "体量/剖面": ("体量", "剖面", "层", "挑空"),
        "可画动作": ("画", "草图", "平面", "标出", "可画"),
    }
    return [name for name, terms in dimensions.items() if any(term in (text or "") for term in terms)]


def _degradation(text: str) -> list[str]:
    hits = []
    if any(term in (text or "") for term in ("无法判断", "信息不足，无法", "不能给出建议")):
        hits.append("无法判断式退化")
    if any(term in (text or "") for term in ("Candidate Commitment Boundary", "内部检查结果", "内部生成前约束")):
        hits.append("内部规则外显")
    if (text or "").count("需要确认") + (text or "").count("需要验证") >= 6:
        hits.append("条件句膨胀")
    return hits


def run_dialogue(title: str, prompts: tuple[str, ...]) -> list[dict]:
    state = empty_state()
    history: list[dict] = []
    rows = []
    for turn, user in enumerate(prompts, 1):
        result = ac.chat_turn(user, history, state, turn_id=turn, capture_stages=True)
        reply = result.get("reply") or ""
        state = result.get("state") or state
        confirmed = "\n".join(
            str(item.get("value") or item.get("text") or "") if isinstance(item, dict) else str(item)
            for item in state.get("student_decisions") or []
        )
        stages = result.get("stages") or {}
        rows.append({
            "title": title,
            "turn": turn,
            "user": user,
            "reply": reply,
            "status": stages.get("candidate_commitment_status", ""),
            "question_patched": bool(stages.get("candidate_route_question_patched")),
            "unowned_questions": _unowned_route_questions(reply, user, confirmed),
            "fixation": _fixation_hits(reply),
            "labor": _labor(reply),
            "degradation": _degradation(reply),
            "confirmed": confirmed,
        })
        history.extend((
            {"role": "user", "content": user},
            {"role": "assistant", "content": reply},
        ))
    return rows


def write_report(rows: list[dict]) -> None:
    unowned = sum(len(row["unowned_questions"]) for row in rows)
    fixation = sum(len(row["fixation"]) for row in rows)
    degraded = sum(bool(row["degradation"]) for row in rows)
    labor = sum(len(row["labor"]) for row in rows)
    lines = [
        "# 提问式隐性路线修复双轮模拟测试报告",
        "",
        f"日期：{datetime.now().strftime('%Y-%m-%d')}",
        "",
        "设置：真实筑思生成链；Candidate Commitment Boundary 开启；Experience Boundary、Experience Patch、PIL、Design State 关闭。",
        "",
        "## 自动观察汇总",
        "",
        f"- AI 自建分类式问题：{unowned}",
        f"- 候选固化：{fixation}",
        f"- 设计劳动覆盖：{labor}/{len(rows) * 4}",
        f"- 退化轮次：{degraded}/{len(rows)}",
        "",
        "自动统计只负责定位，最终结论需阅读完整对话。",
        "",
    ]
    current = None
    for row in rows:
        if row["title"] != current:
            current = row["title"]
            lines.extend((f"## {current}", ""))
        lines.extend((
            f"### 第 {row['turn']} 轮",
            "",
            f"**学生：** {row['user']}",
            "",
            "**筑思 Agent：**",
            "",
            row["reply"],
            "",
            f"观察：status={row['status'] or '无'}；问题局部改写={'是' if row['question_patched'] else '否'}；"
            f"AI 自建分类问题={row['unowned_questions'] or '无'}；候选固化={row['fixation'] or '无'}；"
            f"设计劳动={'、'.join(row['labor']) or '无'}；退化={'、'.join(row['degradation']) or '无'}。",
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
    rows: list[dict] = []
    try:
        ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = True
        ac.ENABLE_EXPERIENCE_BOUNDARY = False
        ac.ENABLE_EXPERIENCE_PATCH_EXECUTION = False
        ac.ENABLE_PIL_MIDDLEWARE = False
        ac.ENABLE_DESIGN_STATE_SUMMARY = False
        for title, prompts in RUNS:
            rows.extend(run_dialogue(title, prompts))
            write_report(rows)
    finally:
        ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = old["candidate"]
        ac.ENABLE_EXPERIENCE_BOUNDARY = old["experience"]
        ac.ENABLE_EXPERIENCE_PATCH_EXECUTION = old["patch"]
        ac.ENABLE_PIL_MIDDLEWARE = old["pil"]
        ac.ENABLE_DESIGN_STATE_SUMMARY = old["design_state"]
        write_report(rows)

    print(f"report={OUT.resolve()}")
    print(f"turns={len(rows)}")
    print(f"unowned_route_questions={sum(len(row['unowned_questions']) for row in rows)}")
    print(f"candidate_fixation={sum(len(row['fixation']) for row in rows)}")
    print(f"design_labor={sum(len(row['labor']) for row in rows)}/{len(rows) * 4}")
    print(f"degraded_turns={sum(bool(row['degradation']) for row in rows)}/{len(rows)}")


if __name__ == "__main__":
    main()
