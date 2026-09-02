"""PIL-4 experience grading experiment.

Compares:
A = PIL-1 all professional experience degradation
B = graded professional experience degradation

No production code is edited by this script. It temporarily monkey-patches the
existing experiment hook only while B-group runs.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

import architect_chat as ac
from conversation_state import empty_state


OUT = Path("output/pil4_experience_grading_experiment_20260821.md")

GRADED_EXPERIENCE_POLICY = """PIL-4 专业经验分级层（内部执行，不展示分级，不输出五栏）：

不要把所有专业经验统一降级。按以下等级处理：

A级：硬约束相关经验
范围：结构、消防、安全、声学、振动、疏散、无障碍等。
处理：保留验证机制。可以明确指出风险和需要验证的条件；不得直接替学生定最终落位。
表达：如果涉及楼板振动、隔声、疏散、结构荷载等，可以写“需要验证/需要处理/如果条件不满足则调整”。

B级：空间组织经验
范围：入口、功能关系、流线、场地界面、公共/私密、动静分区等。
处理：降级为候选策略。不得把道路、公园、儿童行为直接升级成主入口、最佳景观面、必须/不应该的规则。
表达：使用“可以考虑……”“如果……成立，可以尝试……”“先作为候选……”。

C级：设计语言经验
范围：空间体验、形式表达、氛围、体量意向、路径感、场景塑造等。
处理：保持设计生成自由度。不要因为降级而削弱方案推进；可以积极给空间体验和形式策略。
表达：可以直接给可画的空间骨架、体量策略、剖面可能和体验策略，但不要把它伪装成项目事实。

总要求：
- 不输出分级解释。
- 不输出机械身份说明。
- 不输出五栏报告。
- 不写长篇免责声明。
- 仍然要像建筑导师一样推进设计，给出具体空间组织方向。
"""

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


def apply_graded_policy(policy: str) -> str:
    return (policy + "\n" + GRADED_EXPERIENCE_POLICY).strip()


def final_reply(result: dict) -> str:
    return result.get("reply") or ""


def run_dialogue(dialogue: dict, variant: str) -> dict:
    old_pil = ac.ENABLE_PIL1_DEGRADATION
    old_check = ac.ENABLE_PREOUTPUT_CHECK
    old_apply = ac._apply_pil1_degradation_policy
    ac.ENABLE_PREOUTPUT_CHECK = True
    state = empty_state()
    history: list[dict] = []
    turns = []
    try:
        if variant == "pil1":
            ac.ENABLE_PIL1_DEGRADATION = True
        elif variant == "graded":
            ac.ENABLE_PIL1_DEGRADATION = False
            ac._apply_pil1_degradation_policy = apply_graded_policy
        else:
            raise ValueError(f"unknown variant: {variant}")
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
                "intent": result.get("intent", ""),
                "model_status": result.get("model_status", ""),
            })
    finally:
        ac.ENABLE_PIL1_DEGRADATION = old_pil
        ac.ENABLE_PREOUTPUT_CHECK = old_check
        ac._apply_pil1_degradation_policy = old_apply
    return {"turns": turns, "state": deepcopy(state)}


def dialogue_text(run: dict) -> str:
    return "\n\n".join(turn["reply"] for turn in run["turns"])


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
        "导师式推进": ["我先", "你可以", "下一步", "先画", "判断", "可修改", "示范", "收束"],
    }
    present = [name for name, terms in dimensions.items() if contains_any(text, terms)]
    return len(present), present


def disclaimer_flags(text: str) -> list[str]:
    flags = []
    if "无法判断" in text or "不能判断" in text or "信息不足" in text:
        flags.append("信息不足式退化")
    if "A级" in text or "B级" in text or "C级" in text:
        flags.append("分级外显")
    if "项目事实" in text and "专业经验" in text:
        flags.append("机械身份解释")
    if text.count("无法确定") >= 2:
        flags.append("大量无法确定")
    if text.count("需要") >= 18 and len(text) > 1800:
        flags.append("免责声明/条件膨胀")
    return flags


def excerpt(text: str, limit: int = 1300) -> str:
    return text if len(text) <= limit else text[:limit] + "\n\n...[截断]"


def render_run(label: str, run: dict, dialogue: dict) -> tuple[str, dict]:
    full = dialogue_text(run)
    strong_count, strong_hits = count_strong_assertions(full, dialogue["strong_patterns"])
    labor_count, labor_dims = design_labor_score(full)
    flags = disclaimer_flags(full)
    metrics = {"strong_count": strong_count, "labor_count": labor_count, "flags": flags}
    parts = [
        f"### {label}",
        "",
        f"强经验断言：{strong_count}；命中：{('、'.join(strong_hits) if strong_hits else '无')}",
        "",
        f"设计劳动/导师推进：{labor_count}/5；覆盖：{('、'.join(labor_dims) if labor_dims else '无')}",
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
        "# PIL-4 专业经验分级实验",
        "",
        "## 实验目的",
        "",
        "解决 PIL-1 在真实多轮 Agent 中出现的两个副作用：设计劳动轻微下降、条件/免责声明膨胀。",
        "",
        "## 实验假设",
        "",
        "当前 PIL-1 将所有专业经验统一降级，粒度过粗。将专业经验拆成 A/B/C 级后，硬约束保留验证机制，空间组织经验降级为候选，设计语言经验保持生成自由度，可能同时保留降漂移效果和设计推进能力。",
        "",
        "## A/B 设置",
        "",
        "A 组：PIL-1 全部降级。",
        "",
        "B 组：经验分级降级。",
        "",
        "## B 组分级 Prompt",
        "",
        "```text",
        GRADED_EXPERIENCE_POLICY,
        "```",
        "",
    ]
    totals = {"a_strong": 0, "b_strong": 0, "a_labor": 0, "b_labor": 0, "b_flags": 0, "a_flags": 0}
    for item in results:
        dialogue = item["dialogue"]
        a_rendered, a_metrics = render_run("A：PIL-1 全部降级", item["a"], dialogue)
        b_rendered, b_metrics = render_run("B：经验分级降级", item["b"], dialogue)
        totals["a_strong"] += a_metrics["strong_count"]
        totals["b_strong"] += b_metrics["strong_count"]
        totals["a_labor"] += a_metrics["labor_count"]
        totals["b_labor"] += b_metrics["labor_count"]
        totals["a_flags"] += len(a_metrics["flags"])
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

    if totals["b_strong"] <= totals["a_strong"] and totals["b_labor"] > totals["a_labor"] and totals["b_flags"] < totals["a_flags"]:
        verdict = "支持"
    elif totals["b_strong"] <= totals["a_strong"] and totals["b_labor"] >= totals["a_labor"] and totals["b_flags"] <= totals["a_flags"]:
        verdict = "部分支持"
    else:
        verdict = "不支持"

    parts.extend([
        "## 总体统计",
        "",
        f"- A 强经验断言总数：{totals['a_strong']}",
        f"- B 强经验断言总数：{totals['b_strong']}",
        f"- 强断言是否不高于 A：{'是' if totals['b_strong'] <= totals['a_strong'] else '否'}",
        f"- A 设计劳动/导师推进总分：{totals['a_labor']}/10",
        f"- B 设计劳动/导师推进总分：{totals['b_labor']}/10",
        f"- A 免责声明/退化标记数：{totals['a_flags']}",
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
        a = run_dialogue(dialogue, "pil1")
        print(f"running dialogue {dialogue['id']} B ...")
        b = run_dialogue(dialogue, "graded")
        results.append({"dialogue": dialogue, "a": a, "b": b})
    path = write_report(results)
    print(f"done -> {path}")


if __name__ == "__main__":
    main()
