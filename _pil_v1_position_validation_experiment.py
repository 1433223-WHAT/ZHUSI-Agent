"""PIL-V1 position validation experiment.

No production code is imported or modified. The experiment compares:
A = current PIL-4 style, where graded experience policy is inside generation
B = PIL-4 graded experience is applied before the design generator
"""
from __future__ import annotations

from pathlib import Path
import re

import requests


BASE = Path(__file__).resolve().parent
OUT = Path("output/pil_v1_position_validation_experiment.md")
DEEPSEEK_URL = "https://api.deepseek.com/v1/chat/completions"

STATE_RAG_SIMULATION_PROMPT = """你现在只模拟筑思 Agent 的 State/RAG 输入整理。

不要补充外部资料。
不要生成方案。
只把用户输入整理成：
- 已知项目事实
- 用户目标
- 需要进入设计生成的问题
"""

MINIMAL_TUTOR_PROMPT = """你是一名建筑设计导师。

根据输入，给出一版可修改、可放弃的建筑设计建议。

要求：
- 直接推进设计。
- 输出自然导师式回答。
- 必须包含功能关系、空间骨架、体量策略、剖面可能、可画动作中的至少四项。
- 不要把回答变成审查报告。
- 不要替学生做最终决定。
"""

PIL4_GRADED_PROMPT = """PIL-4 专业经验分级层（内部执行，不展示分级，不输出五栏）：

不要把所有专业经验统一降级。按以下等级处理：

A级：硬约束相关经验
范围：结构、消防、安全、声学、振动、疏散、无障碍等。
处理：保留验证机制。可以明确指出风险和需要验证的条件；不得直接替学生定最终落位。

B级：空间组织经验
范围：入口、功能关系、流线、场地界面、公共/私密、动静分区等。
处理：降级为候选策略。不得把道路、公园、儿童行为直接升级成主入口、最佳景观面、必须/不应该的规则。

C级：设计语言经验
范围：空间体验、形式表达、氛围、体量意向、路径感、场景塑造等。
处理：保持设计生成自由度。可以积极给空间体验和形式策略，但不要把它伪装成项目事实。

总要求：
- 不输出分级解释。
- 不输出机械身份说明。
- 不输出五栏报告。
- 不写长篇免责声明。
- 仍然要像建筑导师一样推进设计，给出具体空间组织方向。
"""

PIL4_PRE_GENERATOR_PROMPT = """你是生成前的 PIL-4 专业经验分级层。

任务：
把 State/RAG 模拟输入中可能进入设计生成的专业经验，先处理成生成可用的约束说明。

要求：
- 不增加新的经验规则。
- 不生成建筑方案。
- 不输出五栏报告。
- 不写免责声明。
- 不做最终设计判断。
- 只输出给 Design Generator 使用的内部输入。

处理方式沿用 PIL-4：

A级：结构、消防、安全、声学、振动、疏散、无障碍等硬约束相关经验。
保留为需要验证或处理的风险条件。

B级：入口、功能关系、流线、场地界面、公共/私密、动静分区等空间组织经验。
降级为候选影响因素，不要升级成主入口、最佳景观面、必须/不应该的规则。

C级：空间体验、形式表达、氛围、体量意向、路径感、场景塑造等设计语言经验。
保持设计生成自由度，允许作为积极的空间方向进入生成。

输出格式：
1. 项目事实
2. 用户目标
3. 可进入生成的候选影响因素
4. 需要验证的硬约束风险
5. 可以自由推进的设计语言方向
"""

CASES = [
    {
        "id": "1",
        "title": "社区文化中心",
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
            "功能.*必须",
            "应该.*全部",
        ],
    },
    {
        "id": "2",
        "title": "幼儿园",
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
        "title": "技术经验：舞蹈教室二层",
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


def load_env() -> dict[str, str]:
    env = {}
    path = BASE / ".env"
    if not path.exists():
        return env
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.lstrip().startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            env[key.strip()] = value.split("#", 1)[0].strip().strip('"').strip("'")
    return env


def call_model(messages: list[dict], max_tokens: int = 1300) -> str:
    key = load_env().get("DEEPSEEK_API_KEY", "")
    if not key:
        raise RuntimeError("Missing DEEPSEEK_API_KEY in .env")
    response = requests.post(
        DEEPSEEK_URL,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={
            "model": "deepseek-chat",
            "messages": messages,
            "temperature": 0.35,
            "max_tokens": max_tokens,
        },
        timeout=120,
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"].strip()


def simulate_state_rag(user_input: str) -> str:
    return call_model([
        {"role": "system", "content": STATE_RAG_SIMULATION_PROMPT},
        {"role": "user", "content": user_input},
    ], max_tokens=800)


def generate_a(user_input: str, state_rag: str) -> str:
    return call_model([
        {"role": "system", "content": MINIMAL_TUTOR_PROMPT},
        {"role": "system", "content": PIL4_GRADED_PROMPT},
        {"role": "user", "content": f"用户原始输入：\n{user_input}\n\nState/RAG模拟：\n{state_rag}"},
    ])


def pre_generator_pil4(state_rag: str) -> str:
    return call_model([
        {"role": "system", "content": PIL4_PRE_GENERATOR_PROMPT},
        {"role": "user", "content": state_rag},
    ], max_tokens=1000)


def generate_b(user_input: str, preprocessed: str) -> str:
    return call_model([
        {"role": "system", "content": MINIMAL_TUTOR_PROMPT},
        {
            "role": "user",
            "content": (
                "用户原始输入：\n"
                f"{user_input}\n\n"
                "PIL-4 已在生成前完成专业经验分级，以下是 Design Generator 可使用的输入：\n"
                f"{preprocessed}"
            ),
        },
    ])


def contains_any(text: str, terms: list[str]) -> bool:
    return any(term in text for term in terms)


def count_strong_assertions(text: str, patterns: list[str]) -> tuple[int, list[str]]:
    hits = []
    for pattern in patterns:
        if re.search(pattern, text):
            hits.append(pattern)
    return len(hits), hits


def design_labor_score(text: str) -> tuple[int, list[str]]:
    dimensions = {
        "功能关系": ["功能", "咖啡", "展览", "活动室", "寝室", "舞蹈", "办公", "后勤", "多功能厅"],
        "空间骨架": ["骨架", "组织", "动线", "公共带", "组团", "庭院", "中庭", "大厅", "街道"],
        "体量策略": ["体量", "一层", "二层", "沿", "围合", "展开", "退让", "转角", "L形", "U形"],
        "剖面可能": ["剖面", "楼板", "隔振", "下层", "上层", "层高", "竖向", "屋顶", "平台"],
        "可画动作": ["画", "草图", "关系图", "平面", "剖面", "先把", "标出"],
        "导师感": ["我先", "你可以", "下一步", "判断", "可修改", "示范", "收束", "方向"],
    }
    present = [name for name, terms in dimensions.items() if contains_any(text, terms)]
    return len(present), present


def disclaimer_flags(text: str) -> list[str]:
    flags = []
    if "无法判断" in text or "不能判断" in text or "信息不足" in text:
        flags.append("信息不足式退化")
    if text.count("需要") >= 16 and len(text) > 1600:
        flags.append("机械条件膨胀")
    if text.count("需要确认") >= 3 or text.count("需要验证") >= 5:
        flags.append("每句确认/验证倾向")
    if "A级" in text or "B级" in text or "C级" in text:
        flags.append("分级外显")
    if "项目事实" in text and "专业经验" in text:
        flags.append("机械化回答")
    return flags


def mechanical_flags(text: str) -> list[str]:
    flags = []
    if text.count("如果") >= 10 and len(text) < 1800:
        flags.append("条件句过密")
    if text.count("可以考虑") >= 8:
        flags.append("候选表达机械重复")
    if "1. 项目事实" in text or "可进入生成的候选影响因素" in text:
        flags.append("内部整理外显")
    if "无法" in text and "判断" in text:
        flags.append("判断退化")
    return flags


def excerpt(text: str, limit: int = 1700) -> str:
    return text if len(text) <= limit else text[:limit] + "\n\n...[截断]"


def run_case(case: dict) -> dict:
    state_rag = simulate_state_rag(case["input"])
    a = generate_a(case["input"], state_rag)
    preprocessed = pre_generator_pil4(state_rag)
    b = generate_b(case["input"], preprocessed)
    return {"case": case, "state_rag": state_rag, "preprocessed": preprocessed, "a": a, "b": b}


def render_variant(label: str, text: str, case: dict) -> tuple[str, dict]:
    strong_count, strong_hits = count_strong_assertions(text, case["strong_patterns"])
    labor_count, labor_dims = design_labor_score(text)
    disclaimers = disclaimer_flags(text)
    mechanical = mechanical_flags(text)
    metrics = {
        "strong_count": strong_count,
        "labor_count": labor_count,
        "disclaimer_count": len(disclaimers),
        "mechanical_count": len(mechanical),
        "disclaimers": disclaimers,
        "mechanical": mechanical,
    }
    rendered = (
        f"### {label}\n\n"
        f"强经验断言：{strong_count}；命中：{('、'.join(strong_hits) if strong_hits else '无')}\n\n"
        f"设计劳动/导师感：{labor_count}/6；覆盖：{('、'.join(labor_dims) if labor_dims else '无')}\n\n"
        f"免责声明/退化：{len(disclaimers)}；{('、'.join(disclaimers) if disclaimers else '无')}\n\n"
        f"机械化回答：{len(mechanical)}；{('、'.join(mechanical) if mechanical else '无')}\n\n"
        f"**输出：**\n\n{excerpt(text)}\n"
    )
    return rendered, metrics


def build_report(results: list[dict]) -> str:
    parts = [
        "# PIL-V1 最小架构验证：PIL 接入位置实验",
        "",
        "## 1. 实验目的",
        "",
        "验证 PIL-4 专业经验分级提前到 Design Generator 之前，是否比在生成阶段内部约束更能降低专业经验强断言，同时保持建筑设计劳动。",
        "",
        "## 2. A/B 设置",
        "",
        "A 组：当前 PIL-4 流程。State/RAG 模拟后，Design Generator 内部接收 PIL-4 专业经验分级约束并直接生成。",
        "",
        "B 组：PIL-4 专业经验分级提前到 Design Generator 之前。链路为：用户输入 -> State/RAG 模拟 -> PIL 经验分级 -> Design Generator -> 输出。",
        "",
        "唯一变量：PIL-4 专业经验分级的位置。不增加新的经验规则，不使用 PIL-5 Boundary Gate。",
        "",
        "## 3. Prompt 差异",
        "",
        "### A 组",
        "",
        "```text",
        "State/RAG 模拟 -> Design Generator + PIL-4 专业经验分级约束 -> 输出",
        "```",
        "",
        "### B 组",
        "",
        "```text",
        "State/RAG 模拟 -> PIL-4 专业经验分级预处理 -> Design Generator -> 输出",
        "```",
        "",
        "## 4. 三案例输出",
        "",
    ]
    totals = {
        "a_strong": 0,
        "b_strong": 0,
        "a_labor": 0,
        "b_labor": 0,
        "a_disclaimer": 0,
        "b_disclaimer": 0,
        "a_mechanical": 0,
        "b_mechanical": 0,
    }
    for item in results:
        case = item["case"]
        a_rendered, a_metrics = render_variant("A：当前 PIL-4 流程", item["a"], case)
        b_rendered, b_metrics = render_variant("B：PIL-4 前置到 Design Generator 之前", item["b"], case)
        totals["a_strong"] += a_metrics["strong_count"]
        totals["b_strong"] += b_metrics["strong_count"]
        totals["a_labor"] += a_metrics["labor_count"]
        totals["b_labor"] += b_metrics["labor_count"]
        totals["a_disclaimer"] += a_metrics["disclaimer_count"]
        totals["b_disclaimer"] += b_metrics["disclaimer_count"]
        totals["a_mechanical"] += a_metrics["mechanical_count"]
        totals["b_mechanical"] += b_metrics["mechanical_count"]
        parts.extend([
            f"## 案例 {case['id']}：{case['title']}",
            "",
            "### State/RAG 模拟",
            "",
            excerpt(item["state_rag"], 900),
            "",
            "### B 组生成前 PIL-4 处理",
            "",
            excerpt(item["preprocessed"], 900),
            "",
            a_rendered,
            "",
            b_rendered,
            "",
        ])
    parts.extend([
        "## 5. 强经验断言统计",
        "",
        f"A 组：{totals['a_strong']}",
        "",
        f"B 组：{totals['b_strong']}",
        "",
        f"B < A：{'是' if totals['b_strong'] < totals['a_strong'] else '否'}",
        "",
        "## 6. 设计劳动保持",
        "",
        f"A 组：{totals['a_labor']}/18",
        "",
        f"B 组：{totals['b_labor']}/18",
        "",
        f"B 不低于 A：{'是' if totals['b_labor'] >= totals['a_labor'] else '否'}",
        "",
        "## 7. 免责声明数量",
        "",
        f"A 组：{totals['a_disclaimer']}",
        "",
        f"B 组：{totals['b_disclaimer']}",
        "",
        f"B 不高于 A：{'是' if totals['b_disclaimer'] <= totals['a_disclaimer'] else '否'}",
        "",
        "## 8. 机械化回答",
        "",
        f"A 组：{totals['a_mechanical']}",
        "",
        f"B 组：{totals['b_mechanical']}",
        "",
        f"B 不高于 A：{'是' if totals['b_mechanical'] <= totals['a_mechanical'] else '否'}",
        "",
        "## 9. 结论",
        "",
    ])
    if totals["b_strong"] < totals["a_strong"] and totals["b_labor"] >= totals["a_labor"] and totals["b_disclaimer"] <= totals["a_disclaimer"] and totals["b_mechanical"] <= totals["a_mechanical"]:
        conclusion = "支持"
        reason = "PIL-4 前置后强经验断言下降，同时设计劳动、免责声明和机械化回答均未恶化。"
    elif totals["b_strong"] <= totals["a_strong"] and totals["b_labor"] >= totals["a_labor"] and totals["b_disclaimer"] <= totals["a_disclaimer"]:
        conclusion = "部分支持"
        reason = "PIL-4 前置后没有损害设计劳动，也没有增加免责声明；但强经验断言未形成明确下降，或机械化表达仍需观察。"
    else:
        conclusion = "不支持"
        reason = "PIL-4 前置没有稳定降低强经验断言，或造成设计劳动下降、免责声明/机械化增加。"
    parts.extend([
        conclusion,
        "",
        reason,
        "",
        "本实验只回答接入位置问题：提前处理经验身份是否比生成后 Boundary Gate 更有效。实验未修改生产代码，未进入正式实现。",
        "",
    ])
    return "\n".join(parts)


def main() -> None:
    results = []
    for case in CASES:
        print(f"running case {case['id']} ...", flush=True)
        results.append(run_case(case))
    report = build_report(results)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(report, encoding="utf-8")
    print(f"done -> {OUT}", flush=True)


if __name__ == "__main__":
    main()
