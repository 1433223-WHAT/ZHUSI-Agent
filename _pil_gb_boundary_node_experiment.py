"""PIL-GB minimal mechanism validation experiment.

Compares:
A = State/RAG -> PIL-V2 context -> Design Generator -> output
B = State/RAG -> PIL-V2 context -> Draft Generator -> PIL Boundary Check -> Final Generator -> output

No production files are modified.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import re
import sys

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))

import architect_chat as ac
from conversation_state import empty_state, update_state
from local_search import local_retrieve


OUT = Path("output/pil_gb_boundary_node_experiment.md")

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
        "title": "幼儿经验→空间规则",
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

BOUNDARY_CHECK_PROMPT = """你是 PIL Boundary Check，只检查专业经验身份，不生成方案。

只检查三类问题：

1. 是否把类型惯例写成必须规则。
例如把“幼儿园常见会重视活动室与室外联系”写成“活动室必须成为核心”。

2. 是否把场地经验写成确定事实。
例如把“道路可能影响到达组织”写成“东侧就是主入口/主要人流方向”。
例如把“公园可能形成外部关系”写成“南侧就是最佳景观面/景观资源”。

3. 是否把工程风险写成禁止条件。
例如把“舞蹈教室二层需要处理振动”写成“舞蹈教室不能放二层/必须放一层”。

不要检查：
- 空间创意
- 体量
- 功能关系
- 设计概念

输出给 Final Generator 的改写要求：
- 如果没有上述问题，输出：无需修改。
- 如果有问题，只列出需要降级的句子和改写方向。
- 不输出五栏。
- 不写免责声明。
- 不要求删掉设计劳动。
"""

FINAL_GENERATOR_PROMPT = """你是 Final Generator。

根据内部草稿和 PIL Boundary Check 结果，输出给学生看的最终建筑导师回答。

要求：
- 只修正 Boundary Check 指出的专业经验身份问题。
- 不削弱空间创意、体量、功能关系、设计概念。
- 不输出检查过程。
- 不输出五栏。
- 不输出 source_type / identity / conditions / generation_strength 字段。
- 不写长篇免责声明。
- 仍然要保留功能关系、空间骨架、体量策略、剖面可能和可画动作。
"""


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
    return "\n".join(lines) if lines else "- 暂无明确 State 事实"


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


def call_deepseek(messages: list[dict], max_tokens: int = 1600, temperature: float = 0.2) -> str:
    if not ac.DEEPSEEK_API_KEY:
        raise RuntimeError("Missing DEEPSEEK_API_KEY")
    response = requests.post(
        ac.DEEPSEEK_URL,
        headers={"Authorization": f"Bearer {ac.DEEPSEEK_API_KEY}", "Content-Type": "application/json"},
        json={
            "model": "deepseek-chat",
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        },
        timeout=120,
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"].strip()


def final_reply(result: dict) -> str:
    return result.get("reply") or ""


def run_with_pil_context(case: dict) -> dict:
    state = update_state(empty_state(), case["input"], 1)
    knowledge = retrieve_current_rag(case["input"])
    pil_context = build_pil_v2_context(case["input"], state, knowledge)
    old_pil_enabled = ac.ENABLE_PIL1_DEGRADATION
    old_apply = ac._apply_pil1_degradation_policy
    try:
        ac.ENABLE_PIL1_DEGRADATION = False

        def _apply(policy: str) -> str:
            return (policy + "\n" + pil_context).strip()

        ac._apply_pil1_degradation_policy = _apply
        result = ac.chat_turn(case["input"], [], empty_state(), turn_id=1, capture_stages=True)
        stages = result.get("stages") or {}
        return {
            "reply": final_reply(result),
            "raw_draft": stages.get("raw_draft") or final_reply(result),
            "checked_draft": stages.get("checked_draft") or "",
            "state_before": deepcopy(state),
            "knowledge_before": deepcopy(knowledge),
            "pil_context": pil_context,
            "intent": result.get("intent", ""),
            "model_status": result.get("model_status", ""),
            "model_error": result.get("model_error", ""),
        }
    finally:
        ac.ENABLE_PIL1_DEGRADATION = old_pil_enabled
        ac._apply_pil1_degradation_policy = old_apply


def run_boundary_check(user_input: str, pil_context: str, draft: str) -> str:
    return call_deepseek([
        {"role": "system", "content": BOUNDARY_CHECK_PROMPT},
        {
            "role": "user",
            "content": (
                "用户输入：\n"
                f"{user_input}\n\n"
                "PIL-V2 context：\n"
                f"{pil_context}\n\n"
                "内部草稿：\n"
                f"{draft}"
            ),
        },
    ], max_tokens=900, temperature=0.1)


def run_final_generator(user_input: str, draft: str, check: str) -> str:
    return call_deepseek([
        {"role": "system", "content": FINAL_GENERATOR_PROMPT},
        {
            "role": "user",
            "content": (
                "用户输入：\n"
                f"{user_input}\n\n"
                "内部草稿：\n"
                f"{draft}\n\n"
                "PIL Boundary Check：\n"
                f"{check}"
            ),
        },
    ], max_tokens=1700, temperature=0.25)


def run_case(case: dict) -> dict:
    a = run_with_pil_context(case)
    boundary_check = run_boundary_check(case["input"], a["pil_context"], a["raw_draft"])
    final = run_final_generator(case["input"], a["raw_draft"], boundary_check)
    b = dict(a)
    b["reply"] = final
    b["boundary_check"] = boundary_check
    return {"case": case, "a": a, "b": b}


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
        flags.append("身份解释倾向")
    return flags


def five_column_flags(text: str) -> list[str]:
    markers = ["项目事实", "专业经验", "适用条件", "允许生成强度", "经验来源类型"]
    return ["五栏化/接口外显"] if sum(1 for marker in markers if marker in text) >= 3 else []


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


def build_report(results: list[dict]) -> str:
    parts = [
        "# PIL-GB 最小机制验证报告",
        "",
        "## 1. 实验目的",
        "",
        "验证 PIL 应该位于一次性生成前，还是作为生成过程中的中间检查节点。",
        "",
        "## 2. 实验设置",
        "",
        "A：State/RAG -> PIL-V2 context -> Design Generator -> 输出。",
        "",
        "B：State/RAG -> PIL-V2 context -> Draft Generator -> PIL Boundary Check -> Final Generator -> 输出。",
        "",
        "PIL Boundary Check 只检查三类专业经验身份问题：类型惯例写成必须规则、场地经验写成确定事实、工程风险写成禁止条件。",
        "",
        "不检查空间创意、体量、功能关系、设计概念。",
        "",
    ]
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
    for item in results:
        case = item["case"]
        a_rendered, a_metrics = render_variant("A：PIL-V2 一次性生成前", item["a"], case)
        b_rendered, b_metrics = render_variant("B：PIL-GB 中间检查节点", item["b"], case)
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
            "### PIL Boundary Check 输出",
            "",
            "```text",
            item["b"].get("boundary_check", ""),
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
        "## 3. 验收统计",
        "",
        f"- 强经验断言：A={totals['a_strong']}，B={totals['b_strong']}，B < A：{'是' if totals['b_strong'] < totals['a_strong'] else '否'}",
        f"- 设计劳动：A={totals['a_labor']}/15，B={totals['b_labor']}/15，B 不低于 A：{'是' if totals['b_labor'] >= totals['a_labor'] else '否'}",
        f"- 免责声明/退化：A={totals['a_disclaimer']}，B={totals['b_disclaimer']}，B 不高于 A：{'是' if totals['b_disclaimer'] <= totals['a_disclaimer'] else '否'}",
        f"- 五栏化：A={totals['a_five']}，B={totals['b_five']}，B 不高于 A：{'是' if totals['b_five'] <= totals['a_five'] else '否'}",
        "",
        "## 4. 结论",
        "",
    ])
    if totals["b_strong"] < totals["a_strong"] and totals["b_labor"] >= totals["a_labor"] and totals["b_disclaimer"] <= totals["a_disclaimer"] and totals["b_five"] == 0:
        verdict = "支持"
        reason = "中间检查节点比一次性生成前 PIL-V2 context 更有效，且未损害设计劳动。"
    elif totals["b_strong"] <= totals["a_strong"] and totals["b_labor"] >= totals["a_labor"] and totals["b_disclaimer"] <= totals["a_disclaimer"]:
        verdict = "部分支持"
        reason = "中间检查节点未明显恶化输出，但强经验断言下降不充分或仍需评审。"
    else:
        verdict = "不支持"
        reason = "中间检查节点未降低强经验断言，或造成设计劳动下降、免责声明膨胀、五栏化。"
    parts.extend([verdict, "", reason, "", "完成后停止，不进入正式架构。", ""])
    return "\n".join(parts)


def main() -> None:
    results = []
    failure = ""
    for case in CASES:
        print(f"running case {case['id']} ...", flush=True)
        try:
            results.append(run_case(case))
        except Exception as exc:
            failure = f"{type(exc).__name__}: {exc}"
            print(f"failed -> {failure}", flush=True)
            break
    OUT.parent.mkdir(parents=True, exist_ok=True)
    if failure:
        report = "\n".join([
            "# PIL-GB 最小机制验证报告",
            "",
            "## 1. 执行状态",
            "",
            "真实 A/B 实验未完成。",
            "",
            "## 2. 已完成内容",
            "",
            "- 已创建独立实验脚本。",
            "- 已复用真实 `architect_chat.chat_turn()` 获取 Draft Generator 草稿。",
            "- 已建立 B 组链路：PIL-V2 context -> Draft Generator -> PIL Boundary Check -> Final Generator。",
            "- 未修改生产代码。",
            "",
            "## 3. 阻断原因",
            "",
            f"外部模型调用失败：{failure}",
            "",
            "本次失败发生在 PIL Boundary Check 阶段。真实生成链路已开始运行，但 DeepSeek 返回 402 Payment Required，无法继续完成三案例 A/B 输出与统计。",
            "",
            "## 4. 结论",
            "",
            "未形成实验结论。",
            "",
            "完成后停止，不进入正式架构。",
            "",
        ])
    else:
        report = build_report(results)
    OUT.write_text(report, encoding="utf-8")
    print(f"done -> {OUT}", flush=True)


if __name__ == "__main__":
    main()
