"""PIL-3 minimal real multi-turn integration experiment.

Runs two 6-turn dialogues through chat_turn:
A = current Agent with PIL-1 switch off
B = same Agent with PIL-1 switch on

Production State/RAG/G/Boundary code is not modified by this script.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

import architect_chat as ac
from conversation_state import empty_state


OUT = Path("output/pil3_multiturn_agent_integration_experiment_20260821.md")

DIALOGUES = [
    {
        "id": "1",
        "title": "文化中心 6 轮完整对话",
        "messages": [
            "我做一个3000㎡社区文化中心，基地东侧是社区道路，南侧是公园，北侧是住宅。功能包括展览、咖啡、多功能厅、舞蹈教室、绘画教室、社区会议室和办公后勤。我希望居民平时路过也愿意进去坐一坐。你先帮我推一个空间组织骨架。",
            "我不想它像很正式的文化馆，更像平时能穿过去、能停留的社区客厅。",
            "入口这块你觉得应该怎么处理？东侧道路和南侧公园哪个更重要？",
            "如果咖啡和展览靠近公园，会不会公共性更强？",
            "舞蹈教室如果在二层，会不会影响下面空间？",
            "你把现在的关系收束成一版可画的平面和剖面策略。",
        ],
        "strong_patterns": [
            "东侧.*主入口",
            "主入口.*东侧",
            "东侧.*主要人流",
            "主要人流.*东侧",
            "南侧.*最佳景观",
            "最佳景观.*南侧",
            "公园.*景观资源",
            "公园.*最大.*资源",
            "南侧.*一定.*打开",
            "舞蹈.*不能.*二层",
            "必须.*放.*一层",
        ],
    },
    {
        "id": "2",
        "title": "幼儿园 6 轮完整对话",
        "messages": [
            "我做一个6班幼儿园，服务3-6岁儿童。我不想做传统长走廊排教室，希望孩子从活动室出来能自然到室外，同时老师方便照看。你帮我推一下活动室、寝室和室外场地关系。",
            "我比较想要孩子一出活动室就能接触室外，但又不要太乱。",
            "活动室是不是应该作为每个班最核心的空间？",
            "寝室要不要也能直接连到庭院？",
            "如果每班都有自己的小院，会不会比一个大场地更好管理？",
            "你把活动室、寝室、室外、公共活动场地收束成一版可画的组团方案。",
        ],
        "strong_patterns": [
            "活动室.*必须.*核心",
            "活动室.*应该.*核心",
            "活动室.*最好.*核心",
            "寝室.*不能.*庭院",
            "寝室.*不能.*室外",
            "寝室.*不应该.*庭院",
            "寝室.*不应该.*室外",
            "每班.*必须.*独立",
            "每个班.*必须.*独立",
            "孩子.*一定.*乱",
        ],
    },
]


def final_reply(result: dict) -> str:
    return result.get("reply") or ""


def run_dialogue(dialogue: dict, enable_pil: bool) -> dict:
    old_pil = ac.ENABLE_PIL1_DEGRADATION
    old_check = ac.ENABLE_PREOUTPUT_CHECK
    ac.ENABLE_PIL1_DEGRADATION = enable_pil
    ac.ENABLE_PREOUTPUT_CHECK = True
    state = empty_state()
    history: list[dict] = []
    turns = []
    try:
        for idx, message in enumerate(dialogue["messages"], start=1):
            result = ac.chat_turn(message, history, state, turn_id=idx, capture_stages=True)
            reply = final_reply(result)
            state = result["state"]
            history.append({"role": "user", "content": message})
            history.append({"role": "assistant", "content": reply})
            turns.append({
                "turn": idx,
                "user": message,
                "reply": reply,
                "raw_draft": (result.get("stages") or {}).get("raw_draft", ""),
                "preoutput_check_applied": (result.get("stages") or {}).get("preoutput_check_applied", False),
                "intent": result.get("intent", ""),
                "model_status": result.get("model_status", ""),
            })
    finally:
        ac.ENABLE_PIL1_DEGRADATION = old_pil
        ac.ENABLE_PREOUTPUT_CHECK = old_check
    return {"turns": turns, "state": deepcopy(state)}


def count_strong_assertions(text: str, patterns: list[str]) -> tuple[int, list[str]]:
    hits = []
    for pattern in patterns:
        if re.search(pattern, text):
            hits.append(pattern)
    return len(hits), hits


def contains_any(text: str, terms: list[str]) -> bool:
    return any(term in text for term in terms)


def design_labor_score(text: str) -> tuple[int, list[str]]:
    dimensions = {
        "功能关系": ["功能", "咖啡", "展览", "活动室", "寝室", "舞蹈", "办公", "后勤", "多功能厅"],
        "空间骨架": ["骨架", "组织", "动线", "公共带", "组团", "庭院", "中庭", "大厅", "街道"],
        "体量策略": ["体量", "一层", "二层", "沿", "围合", "展开", "退让", "转角", "L形", "U形"],
        "剖面可能性": ["剖面", "楼板", "隔振", "下层", "上层", "层高", "竖向", "屋顶", "平台"],
    }
    present = [name for name, terms in dimensions.items() if contains_any(text, terms)]
    return len(present), present


def disclaimer_flags(text: str) -> list[str]:
    flags = []
    if "无法判断" in text or "不能判断" in text or "信息不足" in text:
        flags.append("信息不足式退化")
    if "项目事实" in text and "专业经验" in text:
        flags.append("机械身份解释")
    if "PIL-1" in text or "专业经验降级层" in text:
        flags.append("PIL 外显")
    if text.count("无法确定") >= 2:
        flags.append("大量无法确定")
    if text.count("需要") >= 18 and len(text) > 1800:
        flags.append("免责声明/条件膨胀")
    return flags


def dialogue_text(run: dict) -> str:
    return "\n\n".join(turn["reply"] for turn in run["turns"])


def excerpt(text: str, limit: int = 1400) -> str:
    return text if len(text) <= limit else text[:limit] + "\n\n...[截断]"


def render_run(label: str, run: dict, dialogue: dict) -> tuple[str, dict]:
    full = dialogue_text(run)
    strong_count, strong_hits = count_strong_assertions(full, dialogue["strong_patterns"])
    labor_count, labor_dims = design_labor_score(full)
    flags = disclaimer_flags(full)
    metrics = {
        "strong_count": strong_count,
        "labor_count": labor_count,
        "flags": flags,
    }
    parts = [
        f"### {label}",
        "",
        f"强经验断言：{strong_count}；命中：{('、'.join(strong_hits) if strong_hits else '无')}",
        "",
        f"设计劳动：{labor_count}/4；覆盖：{('、'.join(labor_dims) if labor_dims else '无')}",
        "",
        f"免责声明/退化：{('、'.join(flags) if flags else '无')}",
        "",
    ]
    for turn in run["turns"]:
        parts.extend([
            f"#### 第 {turn['turn']} 轮",
            "",
            f"**用户：** {turn['user']}",
            "",
            f"**Agent：**",
            "",
            excerpt(turn["reply"]),
            "",
        ])
    return "\n".join(parts), metrics


def build_report(results: list[dict]) -> str:
    parts = [
        "# PIL-3 筑思 Agent 最小真实接入验证",
        "",
        "说明：本实验只做最小真实接入验证，不进入正式重构。生产 State/RAG/G/Boundary 逻辑不改；PIL-1 通过默认关闭开关接入，实验脚本临时打开 B 组。",
        "",
        "## 实验链路",
        "",
        "A：真实多轮用户输入 → 当前筑思 Agent → 输出",
        "",
        "B：真实多轮用户输入 → 当前筑思 Agent + PIL-1 专业经验降级层 → 输出",
        "",
        "## 验收",
        "",
        "- 强经验断言是否下降。",
        "- 设计劳动是否保持。",
        "- 是否出现免责声明膨胀。",
        "",
    ]
    totals = {"a_strong": 0, "b_strong": 0, "a_labor": 0, "b_labor": 0, "b_flags": 0}
    for item in results:
        dialogue = item["dialogue"]
        a_rendered, a_metrics = render_run("A：当前 Agent", item["a"], dialogue)
        b_rendered, b_metrics = render_run("B：当前 Agent + PIL-1", item["b"], dialogue)
        totals["a_strong"] += a_metrics["strong_count"]
        totals["b_strong"] += b_metrics["strong_count"]
        totals["a_labor"] += a_metrics["labor_count"]
        totals["b_labor"] += b_metrics["labor_count"]
        totals["b_flags"] += len(b_metrics["flags"])
        parts.extend([
            f"## 对话 {dialogue['id']}：{dialogue['title']}",
            "",
            a_rendered,
            "",
            b_rendered,
            "",
            "---",
            "",
        ])

    if totals["b_strong"] < totals["a_strong"] and totals["b_labor"] >= 6 and totals["b_flags"] == 0:
        verdict = "支持"
    elif totals["b_strong"] <= totals["a_strong"] and totals["b_labor"] >= 6 and totals["b_flags"] <= 1:
        verdict = "部分支持"
    else:
        verdict = "不支持"

    parts.extend([
        "## 总体统计",
        "",
        f"- A 强经验断言总数：{totals['a_strong']}",
        f"- B 强经验断言总数：{totals['b_strong']}",
        f"- 是否下降：{'是' if totals['b_strong'] < totals['a_strong'] else '否'}",
        f"- A 设计劳动总分：{totals['a_labor']}/8",
        f"- B 设计劳动总分：{totals['b_labor']}/8",
        f"- B 免责声明/退化标记数：{totals['b_flags']}",
        "",
        "## 结论",
        "",
        f"结论：{verdict}。",
        "",
        "实验完成后停止，不进入正式实现。",
    ])
    return "\n".join(parts)


def write_report(results: list[dict]) -> Path:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(build_report(results), encoding="utf-8")
    return OUT


def main() -> None:
    results = []
    for dialogue in DIALOGUES:
        print(f"running dialogue {dialogue['id']} A ...")
        a = run_dialogue(dialogue, enable_pil=False)
        print(f"running dialogue {dialogue['id']} B ...")
        b = run_dialogue(dialogue, enable_pil=True)
        results.append({"dialogue": dialogue, "a": a, "b": b})
    path = write_report(results)
    print(f"done -> {path}")


if __name__ == "__main__":
    main()
