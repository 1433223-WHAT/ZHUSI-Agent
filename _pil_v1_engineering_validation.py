"""PIL-V1 engineering validation.

A = original Agent
B = original Agent with experimental PIL middleware enabled

No State/RAG/G/Boundary code is modified by this script.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

import architect_chat as ac
from conversation_state import empty_state


OUT = Path("output/pil_v1_engineering_validation_report.md")

CASES = [
    {
        "id": "1",
        "title": "社区中心入口与公园关系",
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
        "title": "幼儿园活动室与室外组织",
        "input": (
            "我做一个6班幼儿园，服务3-6岁儿童。我不想做传统长走廊排教室，"
            "希望孩子从活动室出来能自然到室外，同时老师方便照看。"
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
            "每班.*必须.*独立",
            "每个班.*必须.*独立",
            "孩子.*一定.*乱",
        ],
    },
    {
        "id": "3",
        "title": "舞蹈空间楼层关系",
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


def run_case(case: dict, enable_pil: bool) -> dict:
    old_pil = ac.ENABLE_PIL_MIDDLEWARE
    old_precheck = ac.ENABLE_PREOUTPUT_CHECK
    ac.ENABLE_PIL_MIDDLEWARE = enable_pil
    ac.ENABLE_PREOUTPUT_CHECK = True
    try:
        result = ac.chat_turn(case["input"], [], empty_state(), turn_id=1, capture_stages=True)
        stages = result.get("stages") or {}
        return {
            "reply": result.get("reply") or "",
            "intent": result.get("intent", ""),
            "model_status": result.get("model_status", ""),
            "model_error": result.get("model_error", ""),
            "stages": deepcopy(stages),
        }
    finally:
        ac.ENABLE_PIL_MIDDLEWARE = old_pil
        ac.ENABLE_PREOUTPUT_CHECK = old_precheck


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
        "剖面可能": ["剖面", "楼板", "隔振", "下层", "上层", "层高", "竖向", "屋顶", "平台"],
        "可画动作": ["画", "草图", "关系图", "平面", "剖面", "先把", "标出"],
    }
    present = [name for name, terms in dimensions.items() if contains_any(text, terms)]
    return len(present), present


def degradation_flags(text: str) -> list[str]:
    flags = []
    if "无法判断" in text or "不能判断" in text or "信息不足" in text:
        flags.append("信息不足式退化")
    if text.count("需要") >= 16 and len(text) > 1600:
        flags.append("条件/免责声明膨胀")
    if "PIL" in text or "source_type" in text or "generation_strength" in text:
        flags.append("内部字段外显")
    if "项目事实" in text and "专业经验" in text:
        flags.append("五栏/身份解释倾向")
    return flags


def naturalness_score(text: str) -> tuple[int, list[str]]:
    score = 3
    issues = []
    if "source_type" in text or "generation_strength" in text or "PIL" in text:
        score -= 1
        issues.append("内部字段外显")
    if "项目事实" in text and "专业经验" in text:
        score -= 1
        issues.append("身份解释化")
    if text.count("如果") >= 10 and len(text) < 1800:
        score -= 1
        issues.append("条件句偏密")
    return max(score, 0), issues


def excerpt(text: str, limit: int = 1500) -> str:
    return text if len(text) <= limit else text[:limit] + "\n\n...[截断]"


def render_variant(label: str, run: dict, case: dict) -> tuple[str, dict]:
    text = run["reply"]
    strong_count, strong_hits = count_strong_assertions(text, case["strong_patterns"])
    labor_count, labor_dims = design_labor_score(text)
    natural_count, natural_issues = naturalness_score(text)
    degradation = degradation_flags(text)
    metrics = {
        "strong": strong_count,
        "labor": labor_count,
        "natural": natural_count,
        "degradation": len(degradation),
    }
    parts = [
        f"### {label}",
        "",
        f"intent：{run.get('intent', '')}",
        "",
        f"model_status：{run.get('model_status', '')}",
        "",
        f"强经验断言：{strong_count}；命中：{('、'.join(strong_hits) if strong_hits else '无')}",
        "",
        f"设计劳动：{labor_count}/5；覆盖：{('、'.join(labor_dims) if labor_dims else '无')}",
        "",
        f"回答自然度：{natural_count}/3；问题：{('、'.join(natural_issues) if natural_issues else '无')}",
        "",
        f"退化：{len(degradation)}；{('、'.join(degradation) if degradation else '无')}",
        "",
        "**输出：**",
        "",
        excerpt(text),
        "",
    ]
    return "\n".join(parts), metrics


def build_report(results: list[dict]) -> str:
    parts = [
        "# PIL-V1 最小工程实现验证报告",
        "",
        "## 1. 实现范围",
        "",
        "在 `architect_chat.py` 中增加默认关闭的实验版 PIL middleware。",
        "",
        "原 Agent 作为 A/B 对照保留。State、RAG、G Check、Boundary 现有实现未修改。",
        "",
        "实验链路：用户输入 -> State -> RAG -> Draft Generator -> PIL Boundary Check -> Final Generator -> G Check -> Boundary -> 输出。",
        "",
        "PIL Boundary Check 第一版只检查：类型经验写成必须规则、场地经验写成确定事实、工程风险写成绝对禁止。",
        "",
    ]
    totals = {"a_strong": 0, "b_strong": 0, "a_labor": 0, "b_labor": 0, "a_natural": 0, "b_natural": 0, "a_deg": 0, "b_deg": 0}
    for item in results:
        case = item["case"]
        a_rendered, a_metrics = render_variant("A：原 Agent", item["a"], case)
        b_rendered, b_metrics = render_variant("B：PIL Agent", item["b"], case)
        totals["a_strong"] += a_metrics["strong"]
        totals["b_strong"] += b_metrics["strong"]
        totals["a_labor"] += a_metrics["labor"]
        totals["b_labor"] += b_metrics["labor"]
        totals["a_natural"] += a_metrics["natural"]
        totals["b_natural"] += b_metrics["natural"]
        totals["a_deg"] += a_metrics["degradation"]
        totals["b_deg"] += b_metrics["degradation"]
        parts.extend([
            f"## 案例 {case['id']}：{case['title']}",
            "",
            "### B 组 PIL Boundary Check",
            "",
            "```text",
            (item["b"].get("stages") or {}).get("pil_boundary_check", ""),
            "```",
            "",
            a_rendered,
            "",
            b_rendered,
            "",
            "---",
            "",
        ])
    parts.extend([
        "## 2. 总体统计",
        "",
        f"- 强经验断言：A={totals['a_strong']}，B={totals['b_strong']}，B < A：{'是' if totals['b_strong'] < totals['a_strong'] else '否'}",
        f"- 设计劳动：A={totals['a_labor']}/15，B={totals['b_labor']}/15，B 不低于 A：{'是' if totals['b_labor'] >= totals['a_labor'] else '否'}",
        f"- 回答自然度：A={totals['a_natural']}/9，B={totals['b_natural']}/9，B 不低于 A：{'是' if totals['b_natural'] >= totals['a_natural'] else '否'}",
        f"- 退化：A={totals['a_deg']}，B={totals['b_deg']}，B 不高于 A：{'是' if totals['b_deg'] <= totals['a_deg'] else '否'}",
        "",
        "## 3. 结论",
        "",
    ])
    if totals["b_strong"] < totals["a_strong"] and totals["b_labor"] >= totals["a_labor"] and totals["b_deg"] <= totals["a_deg"]:
        verdict = "支持"
    elif totals["b_strong"] <= totals["a_strong"] and totals["b_labor"] >= totals["a_labor"]:
        verdict = "部分支持"
    else:
        verdict = "不支持"
    parts.extend([verdict, "", "完成后停止，不继续扩展实验。", ""])
    return "\n".join(parts)


def main() -> None:
    results = []
    for case in CASES:
        print(f"running case {case['id']} A ...", flush=True)
        a = run_case(case, enable_pil=False)
        print(f"running case {case['id']} B ...", flush=True)
        b = run_case(case, enable_pil=True)
        results.append({"case": case, "a": a, "b": b})
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(build_report(results), encoding="utf-8")
    print(f"done -> {OUT}", flush=True)


if __name__ == "__main__":
    main()
