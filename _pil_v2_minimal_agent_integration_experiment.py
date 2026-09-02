"""PIL-V2 minimal Agent-chain integration experiment.

Default behavior is offline preparation only. To run real A/B generation, pass
--allow-external. The script does not modify production files.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import argparse
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

import architect_chat as ac
from conversation_state import empty_state, update_state
from local_search import local_retrieve


OUT = Path("output/pil_v2_minimal_agent_integration_experiment.md")

CASES = [
    {
        "id": "1",
        "title": "道路→入口 / 公园→景观资源",
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
        "title": "幼儿类型经验→空间规则",
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
        "title": "幼儿园入口与室外组织追问",
        "input": (
            "如果幼儿园基地西侧有城市支路，东侧有一块比较安静的内院，"
            "入口、活动室和室外场地关系可以怎么组织？"
        ),
        "strong_patterns": [
            "西侧.*主入口",
            "主入口.*西侧",
            "东侧.*最佳.*活动",
            "内院.*必须.*活动",
            "活动室.*必须.*靠.*内院",
            "每班.*必须.*独立",
        ],
    },
]


def _knowledge_items(raw: dict, threshold: float = 0.32) -> list[dict]:
    items = []
    for group in ("cases", "concepts", "skills", "judgments"):
        for item in raw.get(group, []) or []:
            score = float(item.get("score") or 0)
            if score >= threshold:
                items.append(item)
    return items[:3]


def retrieve_current_rag(message: str) -> list[dict]:
    try:
        return _knowledge_items(local_retrieve(message, 3))
    except Exception:
        return []


def state_facts_text(state: dict) -> str:
    project = state.get("project", {}) or {}
    lines = []
    for key in ("project_type", "site", "users", "functions", "scale", "goals", "constraints"):
        value = (project.get(key) or {}).get("value")
        if value:
            lines.append(f"- {key}: {value}")
    if not lines:
        return "- 暂无明确 State 事实"
    return "\n".join(lines)


def rag_text(knowledge: list[dict]) -> str:
    if not knowledge:
        return "- 当前检索未返回高匹配知识片段"
    lines = []
    for index, item in enumerate(knowledge, start=1):
        name = item.get("name") or item.get("title") or item.get("id") or f"片段{index}"
        content = item.get("text") or item.get("content") or item.get("summary") or ""
        lines.append(f"- {name}: {content[:220]}")
    return "\n".join(lines)


def infer_user_goal(message: str) -> str:
    if "骨架" in message or "组织" in message:
        return "推进空间组织骨架"
    if "入口" in message:
        return "讨论入口与到达组织"
    if "活动室" in message or "寝室" in message:
        return "讨论幼儿园活动室、寝室与室外关系"
    return "推进当前建筑设计问题"


def build_pil_v2_context(message: str, state: dict, knowledge: list[dict]) -> str:
    """Deterministic experiment-only PIL-V2 interface implementation."""
    entries = []
    if re.search(r"道路|支路|街|东侧|西侧|入口|人流", message):
        entries.append({
            "source_type": "场地经验",
            "identity": "倾向",
            "conditions": "道路或城市界面可能影响到达组织，但主要人流、开口条件、可达性和学生公共性目标尚未共同确认。",
            "generation_strength": "候选策略",
        })
    if re.search(r"公园|绿地|庭院|内院|景观|室外", message):
        entries.append({
            "source_type": "场地经验",
            "identity": "倾向",
            "conditions": "公园、庭院或室外空间可能形成外部关系，但视线、噪声、边界、开放性和管理条件尚未共同确认。",
            "generation_strength": "候选策略",
        })
    if re.search(r"幼儿|儿童|活动室|寝室|老师|照看|班", message):
        entries.append({
            "source_type": "类型经验",
            "identity": "惯例",
            "conditions": "幼儿园类型经验会重视照看、活动室、寝室和室外活动的关系，但具体组织取决于管理方式、安全边界、班级尺度和场地条件。",
            "generation_strength": "候选策略",
        })
    if re.search(r"舞蹈|振动|声学|二层|楼板|结构", message):
        entries.append({
            "source_type": "工程经验",
            "identity": "风险",
            "conditions": "舞蹈教室若位于二层，需要关注楼板振动、隔声、结构传递和下方功能敏感性。",
            "generation_strength": "需要验证",
        })
    if not entries and knowledge:
        entries.append({
            "source_type": "建筑经验",
            "identity": "惯例",
            "conditions": "RAG 片段可作为相关建筑经验参考，但不得直接套用为当前项目结论。",
            "generation_strength": "候选策略",
        })

    parts = [
        "PIL-V2 实验接口上下文（内部执行，不展示字段名，不输出五栏）：",
        "",
        "PIL 输入：",
        "State事实：",
        state_facts_text(state),
        "",
        "RAG知识片段：",
        rag_text(knowledge),
        "",
        f"用户目标：{infer_user_goal(message)}",
        "",
        "PIL 输出：",
    ]
    for entry in entries:
        parts.extend([
            f"- source_type: {entry['source_type']}",
            f"  identity: {entry['identity']}",
            f"  conditions: {entry['conditions']}",
            f"  generation_strength: {entry['generation_strength']}",
            "",
        ])
    parts.extend([
        "Design Generator 读取：",
        "- generation_strength=必须保留：作为不可忽略条件。",
        "- generation_strength=需要验证：写成技术验证和方案处理重点，不升级为禁止。",
        "- generation_strength=候选策略：只能写成可选择方向，不写成最佳、必须、应该或唯一。",
        "- generation_strength=自由生成：允许展开空间概念、体量和体验。",
        "- 输出仍要保持建筑导师式推进，不能退化成条件清单或免责声明。",
    ])
    return "\n".join(parts)


def final_reply(result: dict) -> str:
    return result.get("reply") or ""


def run_variant(case: dict, variant: str) -> dict:
    state = update_state(empty_state(), case["input"], 1)
    knowledge = retrieve_current_rag(case["input"])
    old_pil_enabled = ac.ENABLE_PIL1_DEGRADATION
    old_apply = ac._apply_pil1_degradation_policy
    try:
        ac.ENABLE_PIL1_DEGRADATION = False
        if variant == "b":
            pil_context = build_pil_v2_context(case["input"], state, knowledge)

            def _apply(policy: str) -> str:
                return (policy + "\n" + pil_context).strip()

            ac._apply_pil1_degradation_policy = _apply
        result = ac.chat_turn(case["input"], [], empty_state(), turn_id=1, capture_stages=True)
        return {
            "reply": final_reply(result),
            "state_before": deepcopy(state),
            "knowledge_before": deepcopy(knowledge),
            "pil_context": build_pil_v2_context(case["input"], state, knowledge) if variant == "b" else "",
            "intent": result.get("intent", ""),
            "model_status": result.get("model_status", ""),
            "model_error": result.get("model_error", ""),
        }
    finally:
        ac.ENABLE_PIL1_DEGRADATION = old_pil_enabled
        ac._apply_pil1_degradation_policy = old_apply


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


def disclaimer_flags(text: str) -> list[str]:
    flags = []
    if "无法判断" in text or "不能判断" in text or "信息不足" in text:
        flags.append("信息不足式退化")
    if text.count("需要") >= 16 and len(text) > 1600:
        flags.append("条件/免责声明膨胀")
    if "source_type" in text or "generation_strength" in text or "PIL-V2" in text:
        flags.append("PIL 字段外显")
    if "项目事实" in text and "专业经验" in text:
        flags.append("五栏/身份解释倾向")
    return flags


def five_column_flags(text: str) -> list[str]:
    markers = ["项目事实", "专业经验", "适用条件", "允许生成强度", "经验来源类型"]
    count = sum(1 for marker in markers if marker in text)
    return ["五栏化/接口外显"] if count >= 3 else []


def excerpt(text: str, limit: int = 1700) -> str:
    return text if len(text) <= limit else text[:limit] + "\n\n...[截断]"


def render_variant(label: str, run: dict, case: dict) -> tuple[str, dict]:
    text = run.get("reply", "")
    strong_count, strong_hits = count_strong_assertions(text, case["strong_patterns"])
    labor_count, labor_dims = design_labor_score(text)
    disclaimers = disclaimer_flags(text)
    five_columns = five_column_flags(text)
    metrics = {
        "strong": strong_count,
        "labor": labor_count,
        "disclaimer": len(disclaimers),
        "five_column": len(five_columns),
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
        f"免责声明/退化：{len(disclaimers)}；{('、'.join(disclaimers) if disclaimers else '无')}",
        "",
        f"五栏化：{len(five_columns)}；{('、'.join(five_columns) if five_columns else '无')}",
        "",
        "**输出：**",
        "",
        excerpt(text),
        "",
    ]
    return "\n".join(parts), metrics


def build_report(results: list[dict], executed: bool) -> str:
    parts = [
        "# PIL-V2 最小真实接入实验报告",
        "",
        "## 1. 实验目的",
        "",
        "验证 PIL-V2 接口是否能以实验方式接入真实筑思 Agent 生成链：复用真实 conversation_state.py、architect_chat.py 现有生成流程和当前 RAG 输入格式，不修改生产主链。",
        "",
        "## 2. 实验边界",
        "",
        "- 不修改生产代码。",
        "- 不改 State / RAG / G Check / Boundary 现有实现。",
        "- 不进入正式实现。",
        "- PIL-V2 只作为实验脚本中的临时生成前策略上下文。",
        "- 默认不调用外部模型；只有使用 `--allow-external` 才执行真实 A/B 生成。",
        "",
        "## 3. 实验链路",
        "",
        "A：用户输入 -> State/RAG -> Design Generator -> 输出",
        "",
        "B：用户输入 -> State/RAG -> PIL-V2 接口上下文 -> Design Generator -> 输出",
        "",
        "## 4. PIL-V2 实验接口",
        "",
        "```text",
        "输入：State事实 / RAG知识片段 / 用户目标",
        "输出：source_type / identity / conditions / generation_strength",
        "读取：必须保留 / 需要验证 / 候选策略 / 自由生成",
        "```",
        "",
    ]
    if not executed:
        parts.extend([
            "## 5. 执行状态",
            "",
            "未执行真实 A/B 生成。",
            "",
            "原因：本任务限制为“不调用外部模型，除非明确确认”。脚本已完成，可在明确确认后用 `--allow-external` 运行真实生成实验。",
            "",
            "## 6. 结论",
            "",
            "未形成实验结论；当前只完成最小接入脚本与报告框架。",
            "",
        ])
        return "\n".join(parts)

    totals = {
        "a_strong": 0,
        "b_strong": 0,
        "a_labor": 0,
        "b_labor": 0,
        "a_disclaimer": 0,
        "b_disclaimer": 0,
        "a_five": 0,
        "b_five": 0,
    }
    parts.append("## 5. 三案例输出")
    parts.append("")
    for item in results:
        case = item["case"]
        a_rendered, a_metrics = render_variant("A：现有生成流程", item["a"], case)
        b_rendered, b_metrics = render_variant("B：实验 PIL-V2 接入", item["b"], case)
        totals["a_strong"] += a_metrics["strong"]
        totals["b_strong"] += b_metrics["strong"]
        totals["a_labor"] += a_metrics["labor"]
        totals["b_labor"] += b_metrics["labor"]
        totals["a_disclaimer"] += a_metrics["disclaimer"]
        totals["b_disclaimer"] += b_metrics["disclaimer"]
        totals["a_five"] += a_metrics["five_column"]
        totals["b_five"] += b_metrics["five_column"]
        parts.extend([
            f"## 案例 {case['id']}：{case['title']}",
            "",
            "### B 组 PIL_CONTEXT",
            "",
            "```text",
            item["b"].get("pil_context", ""),
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
        "## 6. 验收统计",
        "",
        f"- 强经验断言：A={totals['a_strong']}，B={totals['b_strong']}，B < A：{'是' if totals['b_strong'] < totals['a_strong'] else '否'}",
        f"- 设计劳动：A={totals['a_labor']}/15，B={totals['b_labor']}/15，B 不低于 A：{'是' if totals['b_labor'] >= totals['a_labor'] else '否'}",
        f"- 免责声明/退化：A={totals['a_disclaimer']}，B={totals['b_disclaimer']}，B 不高于 A：{'是' if totals['b_disclaimer'] <= totals['a_disclaimer'] else '否'}",
        f"- 五栏化：A={totals['a_five']}，B={totals['b_five']}，B 不高于 A：{'是' if totals['b_five'] <= totals['a_five'] else '否'}",
        "",
        "## 7. 结论",
        "",
    ])
    if totals["b_strong"] < totals["a_strong"] and totals["b_labor"] >= totals["a_labor"] and totals["b_disclaimer"] <= totals["a_disclaimer"] and totals["b_five"] == 0:
        verdict = "支持"
        reason = "PIL-V2 接口可以接入真实生成链，并降低强经验断言，同时未损害设计劳动、未造成免责声明膨胀或五栏化。"
    elif totals["b_strong"] <= totals["a_strong"] and totals["b_labor"] >= totals["a_labor"] and totals["b_disclaimer"] <= totals["a_disclaimer"]:
        verdict = "部分支持"
        reason = "PIL-V2 接口可以接入真实生成链，且未明显损害设计劳动；但强经验断言下降或五栏化控制仍需评审。"
    else:
        verdict = "不支持"
        reason = "PIL-V2 接入后未改善强经验断言，或造成设计劳动下降、免责声明膨胀、五栏化。"
    parts.extend([verdict, "", reason, "", "完成后停止，等待评审。", ""])
    return "\n".join(parts)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-external", action="store_true", help="Run real model-backed A/B experiment.")
    args = parser.parse_args()

    results = []
    if args.allow_external:
        for case in CASES:
            print(f"running case {case['id']} A ...", flush=True)
            a = run_variant(case, "a")
            print(f"running case {case['id']} B ...", flush=True)
            b = run_variant(case, "b")
            results.append({"case": case, "a": a, "b": b})
    report = build_report(results, executed=args.allow_external)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(report, encoding="utf-8")
    print(f"done -> {OUT}", flush=True)


if __name__ == "__main__":
    main()
