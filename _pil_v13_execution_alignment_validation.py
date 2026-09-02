"""PIL execution-alignment validation.

Validates the middleware fix that makes Final Generator treat PIL Check as a
mandatory local rewrite constraint.
"""
from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _pil_v11_boundary_logic_validation import CASES, count_hits, degradation, excerpt, labor_score, run_case


OUT = Path("output/pil_v13_execution_alignment_report.md")


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
        "# PIL 工程修复：Final 执行对齐验证报告",
        "",
        "## 1. 修复内容",
        "",
        "本轮只修 Final Generator 执行对齐：降低原 Draft 权重，将 PIL Boundary Check 作为强制局部改写约束。",
        "",
        "PIL Check 输出要求包含：原句问题、身份错误类型、必须降级后的表达方向。",
        "",
        "Final Generator 明确：如果 PIL 指出某句存在身份问题，不允许保留原强断言或同义强断言。",
        "",
        "未新增经验规则，未修改 State/RAG/G Check/Boundary。",
        "",
    ]
    for item in results:
        case = item["case"]
        a_text, a_metrics = render("A：原 Agent", item["a"], case)
        b_text, b_metrics = render("B：PIL Agent 执行对齐修复", item["b"], case)
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
