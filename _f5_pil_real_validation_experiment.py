"""F5 PIL minimum real validation experiment.

This experiment does not modify production code. It uses a minimal prompt-only
DeepSeek A/B setup so it does not send the production system prompt, source
code, State, RAG snippets, history, or user data beyond the three experiment
cases.
"""
from __future__ import annotations

from pathlib import Path
import re

import requests


BASE = Path(__file__).resolve().parent
OUT = Path("output/f5_pil_real_validation_experiment_20260821.md")
DEEPSEEK_URL = "https://api.deepseek.com/v1/chat/completions"

MINIMAL_GENERATOR_PROMPT = """你是一名建筑设计导师。

根据学生输入，给出一版可修改、可放弃的建筑设计建议。

要求：
- 直接推进设计。
- 输出自然导师式回答。
- 必须包含功能关系、空间骨架、体量方向或空间体验策略中的至少三项。
- 不要把回答变成审查报告。
- 不要替学生做最终决定。
"""


def load_env() -> dict:
    env = {}
    path = BASE / ".env"
    if not path.exists():
        return env
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.lstrip().startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            env[key.strip()] = value.split("#", 1)[0].strip().strip('"').strip("'")
    return env

CASES = [
    {
        "id": "1",
        "title": "文化中心：道路 / 公园 / 公共性判断",
        "input": (
            "我做一个3000㎡社区文化中心，基地东侧是社区道路，南侧是公园，北侧是住宅，"
            "功能包括展览、咖啡、多功能厅、舞蹈教室、绘画教室、社区会议室和办公后勤。"
            "我希望居民平时路过也愿意进去坐一坐。你先帮我推一个空间组织骨架。"
        ),
        "drift_patterns": [
            "主入口放东侧最自然",
            "主入口应该放东侧",
            "东侧.*主要入口",
            "公园是.*最佳景观",
            "南侧.*必须.*打开",
            "南侧.*应该.*公共",
            "这条带是建筑对公园的.*脸",
            "公园.*自带",
        ],
    },
    {
        "id": "2",
        "title": "幼儿园：儿童行为 / 活动室 / 寝室 / 室外关系",
        "input": (
            "我做一个6班幼儿园，服务3-6岁儿童。我不想做传统长走廊排教室，"
            "希望孩子从活动室出来能比较自然地到室外活动，同时老师也方便照看。"
            "你帮我推一下活动室、寝室和室外场地的关系。"
        ),
        "drift_patterns": [
            "活动室.*必须.*核心",
            "活动室.*应该.*核心",
            "活动室.*最好.*核心",
            "寝室.*不应该.*庭院",
            "寝室.*不能.*庭院",
            "每个班.*必须.*独立",
            "孩子.*一定",
        ],
    },
    {
        "id": "3",
        "title": "养老中心：新题型泛化",
        "input": (
            "我做一个小型社区养老服务中心，里面有日间照料、康复训练、助餐、阅读休息、"
            "家属探访和办公后勤。基地西侧是城市道路，南侧有一片小广场，北侧是普通住宅。"
            "我想让老人觉得容易到达、愿意停留，也不希望空间太像机构。你帮我推一版空间骨架。"
        ),
        "drift_patterns": [
            "老人.*必须",
            "养老.*必须",
            "康复.*必须.*一层",
            "助餐.*必须.*一层",
            "西侧.*主入口.*最",
            "西侧.*应该.*主入口",
            "南侧.*广场.*最佳",
        ],
    },
]

TYPE_TERMS = {
    "幼儿园": ["活动室核心", "班级单元", "寝室安静", "室外活动场地"],
    "图书馆": ["阅览空间", "中庭", "安静分区"],
    "养老": ["日间照料", "康复训练", "助餐", "探访", "无障碍"],
    "社区养老": ["日间照料", "康复训练", "助餐", "探访", "无障碍"],
    "文化中心": ["公共大厅", "展览", "咖啡", "多功能厅"],
    "社区中心": ["公共大厅", "展览", "咖啡", "多功能厅"],
}

SITE_TERMS = {
    "道路": ["人流方向", "车行停靠", "人行安全", "主次入口关系"],
    "公园": ["视线", "边界开放性", "噪声", "可达性"],
    "广场": ["活动强度", "噪声", "边界开放性", "停留方式"],
    "住宅": ["噪声影响", "隐私边界", "开放时段"],
    "南侧": ["日照", "遮阳", "景观价值", "相邻干扰"],
    "西侧": ["到达方向", "人车关系", "入口等级"],
    "东侧": ["到达方向", "人车关系", "入口等级"],
}

ENGINEERING_TERMS = {
    "舞蹈": ["楼板隔振", "下层功能", "使用时段", "墙体隔声"],
    "康复": ["无障碍尺度", "扶手", "设备尺寸", "护理可达性"],
    "助餐": ["后勤流线", "排烟", "洁污分流", "消防"],
    "噪声": ["隔声", "使用时段", "相邻功能"],
}


def contains_any(text: str, terms: list[str]) -> bool:
    return any(term in text for term in terms)


def professional_identity_check(user_message: str) -> list[dict]:
    warnings: list[dict] = []

    for term, conditions in SITE_TERMS.items():
        if term in user_message:
            warnings.append(
                {
                    "source_type": "场地经验",
                    "claim": f"{term}可能影响入口、公共界面或空间朝向",
                    "conditions": conditions,
                    "direct_expression": "不可以直接表达为确定结论",
                    "allowed_strength": "只能作为条件候选",
                }
            )

    for term, conventions in TYPE_TERMS.items():
        if term in user_message:
            warnings.append(
                {
                    "source_type": "类型经验",
                    "claim": f"{term}的常见组织方式可能被用于生成空间骨架",
                    "conditions": conventions,
                    "direct_expression": "不可以表达为必须遵守的空间规则",
                    "allowed_strength": "只能作为可修改的组织候选",
                }
            )

    for term, conditions in ENGINEERING_TERMS.items():
        if term in user_message:
            warnings.append(
                {
                    "source_type": "工程经验",
                    "claim": f"{term}相关判断可能涉及工程风险",
                    "conditions": conditions,
                    "direct_expression": "不可以压缩为绝对落位规则",
                    "allowed_strength": "只能作为待验证风险或条件候选",
                }
            )

    return warnings[:5]


def pil_policy(user_message: str) -> str:
    warnings = professional_identity_check(user_message)
    if not warnings:
        return ""

    lines = ["Professional Identity Check（实验，内部使用，不展示为表格）："]
    for item in warnings:
        lines.append(
            "- "
            f"经验来源类型：{item['source_type']}；"
            f"判断：{item['claim']}；"
            f"依赖条件：{'、'.join(item['conditions'][:4])}；"
            f"是否可直接表达：{item['direct_expression']}；"
            f"允许建议强度：{item['allowed_strength']}。"
        )
    lines.extend(
        [
            "生成要求：",
            "- 最终回答保持自然导师语言，不展示上述检查表。",
            "- 仍必须给出功能关系、空间骨架、体量方向或空间体验策略。",
            "- 不写长篇免责声明，不退化成“无法判断”。",
        ]
    )
    return "\n".join(lines)


def call_model(user_input: str, pic_summary: str | None) -> str:
    key = load_env().get("DEEPSEEK_API_KEY", "")
    if not key:
        raise RuntimeError("Missing DEEPSEEK_API_KEY in .env")
    messages = [{"role": "system", "content": MINIMAL_GENERATOR_PROMPT}]
    if pic_summary:
        messages.append({"role": "system", "content": pic_summary})
    messages.append({"role": "user", "content": user_input})
    response = requests.post(
        DEEPSEEK_URL,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={"model": "deepseek-chat", "messages": messages, "temperature": 0.35, "max_tokens": 1300},
        timeout=120,
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"].strip()


def final_text(result: str) -> str:
    return result or ""


def count_drift(text: str, patterns: list[str]) -> tuple[int, list[str]]:
    hits = []
    for pattern in patterns:
        if re.search(pattern, text):
            hits.append(pattern)
    return len(hits), hits


def design_labor_score(text: str) -> tuple[int, list[str]]:
    dimensions = {
        "功能关系": ["功能", "咖啡", "展览", "活动室", "寝室", "康复", "助餐", "办公", "后勤"],
        "空间骨架": ["骨架", "组织", "动线", "公共带", "组团", "庭院", "中庭", "大厅"],
        "体量方向": ["体量", "一层", "二层", "沿", "围合", "展开", "退让", "转角"],
        "空间体验策略": ["体验", "停留", "穿行", "看见", "自然", "开放", "安静", "可达"],
    }
    present = [name for name, terms in dimensions.items() if contains_any(text, terms)]
    return len(present), present


def degeneration_flags(text: str) -> list[str]:
    flags = []
    if "经验来源类型" in text or "允许建议强度" in text:
        flags.append("五栏/检查表外显")
    if text.count("无法判断") + text.count("不能判断") >= 1:
        flags.append("无法判断式退化")
    if text.count("需要") >= 10 and len(text) > 1200:
        flags.append("长篇条件/免责声明倾向")
    return flags


def excerpt(text: str, limit: int = 1800) -> str:
    text = text or ""
    return text if len(text) <= limit else text[:limit] + "\n\n...[截断]"


def render_check(warnings: list[dict]) -> str:
    lines = []
    for item in warnings:
        lines.append(
            f"- {item['source_type']}｜{item['claim']}｜缺少/依赖："
            f"{'、'.join(item['conditions'][:4])}｜允许：{item['allowed_strength']}"
        )
    return "\n".join(lines) if lines else "（无高风险专业经验命中）"


def render_variant(label: str, result: dict, case: dict) -> tuple[str, dict]:
    text = final_text(result)
    drift_count, drift_hits = count_drift(text, case["drift_patterns"])
    labor_count, labor_dims = design_labor_score(text)
    flags = degeneration_flags(text)
    metrics = {
        "drift_count": drift_count,
        "drift_hits": drift_hits,
        "labor_count": labor_count,
        "labor_dims": labor_dims,
        "flags": flags,
    }
    rendered = (
        f"### {label}\n\n"
        f"漂移命中：{drift_count}；命中模式：{('、'.join(drift_hits) if drift_hits else '无')}\n\n"
        f"设计劳动：{labor_count}/4；覆盖：{('、'.join(labor_dims) if labor_dims else '无')}\n\n"
        f"退化标记：{('、'.join(flags) if flags else '无')}\n\n"
        f"**输出：**\n\n{excerpt(text)}\n"
    )
    return rendered, metrics


def run_case(case: dict) -> dict:
    b_check = professional_identity_check(case["input"])
    pic = pil_policy(case["input"])
    return {
        "case": case,
        "pil_check": b_check,
        "a": call_model(case["input"], pic_summary=None),
        "b": call_model(case["input"], pic_summary=pic),
    }


def conclusion(results: list[dict]) -> str:
    a_drift = 0
    b_drift = 0
    a_labor = 0
    b_labor = 0
    b_flags = 0
    for item in results:
        case = item["case"]
        a_text = final_text(item["a"])
        b_text = final_text(item["b"])
        a_drift += count_drift(a_text, case["drift_patterns"])[0]
        b_drift += count_drift(b_text, case["drift_patterns"])[0]
        a_labor += design_labor_score(a_text)[0]
        b_labor += design_labor_score(b_text)[0]
        b_flags += len(degeneration_flags(b_text))

    verdict = "支持进入正式 PIL 实现前的更小范围实现验证"
    if b_drift >= a_drift or b_labor < 9 or b_flags:
        verdict = "暂不直接进入正式 PIL 实现，需要先收窄 PIC 注入方式或调整强度"

    return (
        "## 总体量化结果\n\n"
        f"- A 漂移总数：{a_drift}\n"
        f"- B 漂移总数：{b_drift}\n"
        f"- A 设计劳动总分：{a_labor}/12\n"
        f"- B 设计劳动总分：{b_labor}/12\n"
        f"- B 退化标记数：{b_flags}\n\n"
        "## 是否值得进入正式 PIL 实现\n\n"
        f"结论：{verdict}。\n"
    )


def build_report(results: list[dict]) -> str:
    parts = [
        "# F5 Professional Identity Layer 最小真实验证实验",
        "",
        "说明：本实验调用 DeepSeek live 设计输出，但不运行筑思 Agent 生产主链；不修改生产代码，不写 State，不改 RAG / G Check / Boundary，不实现正式 PIL。",
        "",
        "## 实验架构",
        "",
        "A：实验案例输入 → 最小 Design Generator Prompt → DeepSeek 输出",
        "",
        "B：实验案例输入 → Professional Identity Check（实验短约束）→ 最小 Design Generator Prompt → DeepSeek 输出",
        "",
        "Professional Identity Check 只生成内部短约束：经验来源类型、依赖条件、是否可直接表达、允许建议强度。它不生成方案，也不展示给用户。",
        "",
        "数据边界：本实验只发送三条案例文本、最小生成 Prompt 和 B 组 PIC 实验 Prompt；不发送筑思 Agent 完整 SYSTEM_PROMPT，不发送项目源码，不发送 State、RAG、历史对话或其他用户数据。",
        "",
        "## A/B 差异",
        "",
        "- A 使用最小导师生成 Prompt。",
        "- B 在同一最小导师生成 Prompt 前注入临时 PIC 短约束。",
        "- 两组都不调用生产 State / RAG / G / Boundary。",
        "- 三个案例分别验证场地经验、类型经验、工程经验与新题型泛化。",
        "",
    ]

    for item in results:
        case = item["case"]
        a_rendered, _ = render_variant("A：当前原生成链", item["a"], case)
        b_rendered, _ = render_variant("B：增加临时 Professional Identity Check", item["b"], case)
        parts.extend(
            [
                f"## 案例 {case['id']}：{case['title']}",
                "",
                f"**输入：** {case['input']}",
                "",
                "**B 组 PIC 内部输出：**",
                "",
                render_check(item["pil_check"]),
                "",
                a_rendered,
                "",
                b_rendered,
                "",
                "---",
                "",
            ]
        )

    parts.append(conclusion(results))
    return "\n".join(parts)


def write_report(results: list[dict], path: Path = OUT) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build_report(results), encoding="utf-8")
    return path


def main() -> None:
    results = []
    for case in CASES:
        print(f"running case {case['id']} ...")
        results.append(run_case(case))
    path = write_report(results)
    print(f"done -> {path}")


if __name__ == "__main__":
    main()
