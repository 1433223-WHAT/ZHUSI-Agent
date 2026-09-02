"""PIL-2 minimal integration validation for the ArchAI generation chain.

This is an experiment only. It imports the existing generation function, keeps
State/RAG/G/Boundary code unchanged, and varies only the response policy:
A = current generation policy
B = current generation policy + PIL-1 experience degradation layer
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

import architect_chat as ac
from conversation_state import empty_state


OUT = Path("output/pil2_agent_chain_minimal_integration_experiment_20260821.md")

BASE_POLICY = "每轮优先产生建筑推进量；示范骨架声明可接受、修改、组合或放弃；不要把设计任务退回给学生。"

PIL1_DEGRADATION_POLICY = """PIL-1 专业经验降级层（内部执行，不展示为身份解释，不输出五栏）：

在生成设计建议前，请区分：
1. 项目事实：用户明确提供的信息。
2. 专业经验：建筑领域常见做法、类型经验、工程考虑。

专业经验只能作为候选影响因素，不能直接升级为项目结论。

生成时遵守：
- 道路、街道、城市界面：只能说明可能影响到达组织，不能直接推出主入口、主要人流方向。
- 公园、绿地、庭院：只能说明存在潜在外部关系，不能直接推出安静、景观资源、最佳朝向。
- 儿童、幼儿、照看、安全：只能说明需要考虑管理条件，不能直接推出必须、不应该的空间规则。
- 舞蹈、声学、振动、结构：只能说明存在技术风险和条件依赖，不能直接推出不能放二层、必须放一层。

如果设计建议依赖专业经验，请保留为候选策略：
“可以考虑……”
“如果……成立，可以尝试……”
“需要结合……进一步验证。”

不要输出身份解释。
不要输出五栏。
不要减少设计建议。
仍然需要给出具体空间组织方向。
"""

CASES = [
    {
        "id": "1",
        "title": "社区中心：道路到入口",
        "input": (
            "我做一个3000㎡社区文化中心，基地东侧是社区道路，南侧是公园，北侧是住宅。"
            "功能包括展览、咖啡、多功能厅、舞蹈教室、绘画教室、社区会议室和办公后勤。"
            "我希望居民平时路过也愿意进去坐一坐。你先帮我推一个空间组织骨架。"
        ),
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
        ],
    },
    {
        "id": "2",
        "title": "幼儿园：儿童经验到空间规则",
        "input": (
            "我做一个6班幼儿园，服务3-6岁儿童。"
            "我不想做传统长走廊排教室，希望孩子从活动室出来能自然到室外，同时老师方便照看。"
            "你帮我推一下活动室、寝室和室外场地关系。"
        ),
        "strong_patterns": [
            "活动室.*必须.*核心",
            "活动室.*应该.*核心",
            "活动室.*最好.*核心",
            "寝室.*不能.*庭院",
            "寝室.*不能.*室外",
            "寝室.*不应该.*庭院",
            "寝室.*不应该.*室外",
            "每班.*必须.*独立出口",
            "每个班.*必须.*独立出口",
        ],
    },
    {
        "id": "3",
        "title": "舞蹈教室：技术经验到楼层规则",
        "input": "一个社区文化中心包含舞蹈教室。如果舞蹈教室放在二层，需要注意什么？",
        "strong_patterns": [
            "舞蹈.*不能.*二层",
            "舞蹈.*不适合.*二层",
            "不能.*放在二层",
            "必须.*放.*一层",
            "最好.*放.*一层",
            "应该.*放.*一层",
        ],
    },
]


def build_state() -> dict:
    return empty_state()


def run_variant(case: dict, policy: str) -> dict:
    old_check = ac.ENABLE_PREOUTPUT_CHECK
    ac.ENABLE_PREOUTPUT_CHECK = True
    try:
        result = ac._call_deepseek(
            [{"role": "user", "content": case["input"]}],
            build_state(),
            [],
            "design_development",
            [],
            policy,
            return_stages=True,
        )
    finally:
        ac.ENABLE_PREOUTPUT_CHECK = old_check
    return deepcopy(result)


def run_case(case: dict) -> dict:
    return {
        "case": case,
        "a": run_variant(case, BASE_POLICY),
        "b": run_variant(case, BASE_POLICY + "\n\n" + PIL1_DEGRADATION_POLICY),
    }


def final_text(result: dict) -> str:
    return result.get("final_after_boundary") or result.get("reply") or ""


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
    if text.count("需要") >= 12 and len(text) > 1200:
        flags.append("免责声明/条件膨胀")
    return flags


def excerpt(text: str, limit: int = 1800) -> str:
    return text if len(text) <= limit else text[:limit] + "\n\n...[截断]"


def render_variant(label: str, result: dict, case: dict) -> tuple[str, dict]:
    text = final_text(result)
    strong_count, strong_hits = count_strong_assertions(text, case["strong_patterns"])
    labor_count, labor_dims = design_labor_score(text)
    flags = disclaimer_flags(text)
    metrics = {
        "strong_count": strong_count,
        "labor_count": labor_count,
        "flags": flags,
    }
    rendered = (
        f"### {label}\n\n"
        f"强经验断言：{strong_count}；命中：{('、'.join(strong_hits) if strong_hits else '无')}\n\n"
        f"设计劳动：{labor_count}/4；覆盖：{('、'.join(labor_dims) if labor_dims else '无')}\n\n"
        f"免责声明/退化：{('、'.join(flags) if flags else '无')}\n\n"
        f"preoutput_check_applied：{result.get('preoutput_check_applied')}\n\n"
        f"**raw_draft：**\n\n{excerpt(result.get('raw_draft', ''))}\n\n"
        f"**final_after_boundary：**\n\n{excerpt(text)}\n"
    )
    return rendered, metrics


def build_report(results: list[dict]) -> str:
    parts = [
        "# PIL-2 筑思 Agent 生成链最小接入验证",
        "",
        "说明：本实验不修改生产代码，不进入正式部署。State/RAG/G/Boundary 代码保持不变；只在 B 组通过 response policy 追加 PIL-1 专业经验降级层。",
        "",
        "## 实验链路",
        "",
        "A：用户输入 → 当前筑思生成流程 → 输出",
        "",
        "B：用户输入 → 当前筑思生成流程 + PIL-1 经验降级层 → 输出",
        "",
        "## B 组新增层",
        "",
        "```text",
        PIL1_DEGRADATION_POLICY,
        "```",
        "",
    ]
    totals = {"a_strong": 0, "b_strong": 0, "a_labor": 0, "b_labor": 0, "b_flags": 0}
    for item in results:
        case = item["case"]
        a_rendered, a_metrics = render_variant("A：当前筑思生成流程", item["a"], case)
        b_rendered, b_metrics = render_variant("B：当前筑思生成流程 + PIL-1", item["b"], case)
        totals["a_strong"] += a_metrics["strong_count"]
        totals["b_strong"] += b_metrics["strong_count"]
        totals["a_labor"] += a_metrics["labor_count"]
        totals["b_labor"] += b_metrics["labor_count"]
        totals["b_flags"] += len(b_metrics["flags"])
        parts.extend([
            f"## 案例 {case['id']}：{case['title']}",
            "",
            f"**输入：** {case['input']}",
            "",
            a_rendered,
            "",
            b_rendered,
            "",
            "---",
            "",
        ])

    if totals["b_strong"] < totals["a_strong"] and totals["b_labor"] >= 9 and totals["b_flags"] == 0:
        verdict = "支持"
    elif totals["b_strong"] <= totals["a_strong"] and totals["b_labor"] >= 9 and totals["b_flags"] <= 1:
        verdict = "部分支持"
    else:
        verdict = "不支持"

    parts.extend([
        "## 总体统计",
        "",
        f"- A 强经验断言总数：{totals['a_strong']}",
        f"- B 强经验断言总数：{totals['b_strong']}",
        f"- 是否下降：{'是' if totals['b_strong'] < totals['a_strong'] else '否'}",
        f"- A 设计劳动总分：{totals['a_labor']}/12",
        f"- B 设计劳动总分：{totals['b_labor']}/12",
        f"- B 免责声明/退化标记数：{totals['b_flags']}",
        "",
        "## 结论",
        "",
        f"结论：{verdict}。",
        "",
        "本实验完成后停止，不进入正式实现。",
    ])
    return "\n".join(parts)


def write_report(results: list[dict]) -> Path:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(build_report(results), encoding="utf-8")
    return OUT


def main() -> None:
    results = []
    for case in CASES:
        print(f"running case {case['id']} ...")
        results.append(run_case(case))
    path = write_report(results)
    print(f"done -> {path}")


if __name__ == "__main__":
    main()
