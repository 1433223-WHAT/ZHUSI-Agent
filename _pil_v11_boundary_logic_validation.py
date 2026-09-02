"""PIL-V1.1 boundary logic validation.

Only validates the updated PIL Boundary Check logic.
"""
from __future__ import annotations

from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

import architect_chat as ac
from conversation_state import empty_state


OUT = Path("output/pil_v11_boundary_logic_validation_report.md")

CASES = [
    {
        "id": "1",
        "title": "道路→入口",
        "input": (
            "我做一个3000㎡社区文化中心，基地东侧是社区道路，北侧是住宅。"
            "功能包括展览、咖啡、多功能厅、舞蹈教室、绘画教室、社区会议室和办公后勤。"
            "我希望居民平时路过也愿意进去坐一坐。你先帮我推一个入口和空间组织骨架。"
        ),
        "strong_patterns": ["东侧.*主入口", "主入口.*东侧", "东侧.*主要人流", "主要人流.*东侧"],
    },
    {
        "id": "2",
        "title": "公园→景观",
        "input": (
            "我做一个3000㎡社区文化中心，基地南侧是公园，东侧是社区道路，北侧是住宅。"
            "功能包括展览、咖啡、多功能厅、绘画教室、社区会议室和办公后勤。"
            "我希望它有日常停留感。你先帮我推一个空间组织骨架。"
        ),
        "strong_patterns": ["南侧.*最佳景观", "最佳景观.*南侧", "公园.*景观资源", "公园.*最大.*资源", "南侧.*一定.*打开"],
    },
    {
        "id": "3",
        "title": "舞蹈→工程风险",
        "input": "一个社区文化中心包含舞蹈教室。如果舞蹈教室放在二层，需要注意什么？",
        "strong_patterns": ["舞蹈.*不能.*二层", "舞蹈.*不适合.*二层", "不能.*放在二层", "必须.*放.*一层", "最好.*放.*一层", "应该.*放.*一层"],
    },
]


def run_case(case: dict, enable_pil: bool) -> dict:
    old_pil = ac.ENABLE_PIL_MIDDLEWARE
    old_precheck = ac.ENABLE_PREOUTPUT_CHECK
    ac.ENABLE_PIL_MIDDLEWARE = enable_pil
    ac.ENABLE_PREOUTPUT_CHECK = True
    try:
        result = ac.chat_turn(case["input"], [], empty_state(), turn_id=1, capture_stages=True)
        return {"reply": result.get("reply") or "", "stages": result.get("stages") or {}, "status": result.get("model_status", "")}
    finally:
        ac.ENABLE_PIL_MIDDLEWARE = old_pil
        ac.ENABLE_PREOUTPUT_CHECK = old_precheck


def count_hits(text: str, patterns: list[str]) -> tuple[int, list[str]]:
    hits = [pattern for pattern in patterns if re.search(pattern, text)]
    return len(hits), hits


def has_any(text: str, terms: list[str]) -> bool:
    return any(term in text for term in terms)


def labor_score(text: str) -> tuple[int, list[str]]:
    dims = {
        "功能关系": ["功能", "咖啡", "展览", "活动室", "寝室", "舞蹈", "办公", "后勤", "多功能厅"],
        "空间骨架": ["骨架", "组织", "动线", "公共带", "组团", "庭院", "中庭", "大厅", "街道"],
        "体量策略": ["体量", "一层", "二层", "沿", "围合", "展开", "退让", "转角", "L形", "U形"],
        "剖面可能": ["剖面", "楼板", "隔振", "下层", "上层", "层高", "竖向", "屋顶", "平台"],
        "可画动作": ["画", "草图", "关系图", "平面", "剖面", "先把", "标出"],
    }
    present = [name for name, terms in dims.items() if has_any(text, terms)]
    return len(present), present


def degradation(text: str) -> list[str]:
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


def excerpt(text: str, limit: int = 1400) -> str:
    return text if len(text) <= limit else text[:limit] + "\n\n...[截断]"


def render(label: str, run: dict, case: dict) -> tuple[str, dict]:
    strong, hits = count_hits(run["reply"], case["strong_patterns"])
    labor, dims = labor_score(run["reply"])
    deg = degradation(run["reply"])
    metrics = {"strong": strong, "labor": labor, "deg": len(deg)}
    text = "\n".join([
        f"### {label}",
        "",
        f"强经验断言：{strong}；命中：{('、'.join(hits) if hits else '无')}",
        "",
        f"设计劳动：{labor}/5；覆盖：{('、'.join(dims) if dims else '无')}",
        "",
        f"退化：{len(deg)}；{('、'.join(deg) if deg else '无')}",
        "",
        "**输出：**",
        "",
        excerpt(run["reply"]),
        "",
    ])
    return text, metrics


def build_report(results: list[dict]) -> str:
    totals = {"a_strong": 0, "b_strong": 0, "a_labor": 0, "b_labor": 0, "a_deg": 0, "b_deg": 0}
    parts = [
        "# PIL-V1.1 Boundary Check 最小修正验证报告",
        "",
        "## 1. 修正内容",
        "",
        "只修改 PIL Boundary Check 判断逻辑：从检查“必须/确定/禁止”升级为检查“专业经验到设计结论之间是否缺少成立条件”。",
        "",
        "未修改 State、RAG、G Check、Boundary，未新增架构。",
        "",
    ]
    for item in results:
        case = item["case"]
        a_text, a_metrics = render("A：原 Agent", item["a"], case)
        b_text, b_metrics = render("B：PIL-V1.1", item["b"], case)
        totals["a_strong"] += a_metrics["strong"]
        totals["b_strong"] += b_metrics["strong"]
        totals["a_labor"] += a_metrics["labor"]
        totals["b_labor"] += b_metrics["labor"]
        totals["a_deg"] += a_metrics["deg"]
        totals["b_deg"] += b_metrics["deg"]
        parts.extend([
            f"## 案例 {case['id']}：{case['title']}",
            "",
            "### B 组 PIL Boundary Check",
            "",
            "```text",
            item["b"]["stages"].get("pil_boundary_check", ""),
            "```",
            "",
            a_text,
            "",
            b_text,
            "",
            "---",
            "",
        ])
    verdict = "支持" if totals["b_strong"] < totals["a_strong"] and totals["b_labor"] >= totals["a_labor"] and totals["b_deg"] <= totals["a_deg"] else "不支持"
    parts.extend([
        "## 2. 统计",
        "",
        f"- 强经验断言：A={totals['a_strong']}，B={totals['b_strong']}，B < A：{'是' if totals['b_strong'] < totals['a_strong'] else '否'}",
        f"- 设计劳动：A={totals['a_labor']}/15，B={totals['b_labor']}/15，B 不低于 A：{'是' if totals['b_labor'] >= totals['a_labor'] else '否'}",
        f"- 退化：A={totals['a_deg']}，B={totals['b_deg']}，B 不高于 A：{'是' if totals['b_deg'] <= totals['a_deg'] else '否'}",
        "",
        "## 3. 结论",
        "",
        verdict,
        "",
        "完成后停止。",
        "",
    ])
    return "\n".join(parts)


def main() -> None:
    results = []
    for case in CASES:
        print(f"running case {case['id']} A ...", flush=True)
        a = run_case(case, False)
        print(f"running case {case['id']} B ...", flush=True)
        b = run_case(case, True)
        results.append({"case": case, "a": a, "b": b})
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(build_report(results), encoding="utf-8")
    print(f"done -> {OUT}", flush=True)


if __name__ == "__main__":
    main()
