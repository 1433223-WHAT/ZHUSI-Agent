"""PIL-5 Boundary Gate minimal experiment.

No production code is imported or modified. The experiment compares:
A = PIL-4 graded experience generation
B = PIL-4 graded experience generation + lightweight post-output Boundary Gate
"""
from __future__ import annotations

from pathlib import Path
import re

import requests


BASE = Path(__file__).resolve().parent
OUT = Path("output/pil5_boundary_gate_experiment_20260821.md")
DEEPSEEK_URL = "https://api.deepseek.com/v1/chat/completions"

MINIMAL_TUTOR_PROMPT = """你是一名建筑设计导师。

根据学生输入，给出一版可修改、可放弃的建筑设计建议。

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

BOUNDARY_GATE_PROMPT = """你是 PIL-5 Boundary Gate，只做输出前轻量改写。

不要展示检查过程。
不要输出五栏。
不要生成免责声明。
不要减少建筑设计劳动。

只检查以下情况：

1. 经验是否被写成事实。
如果出现经验 → 确定结论，则降低表达强度。
例如：
“东侧道路应该作为主入口。”
改为：
“如果东侧承担主要到达，可以考虑作为入口候选。”

重点检查：
- 南向最好
- 公园适合打开
- 道路适合入口
- 幼儿园必须这样
- 图书馆应该这样
- 某空间不能放某层
- 某功能必须靠某侧

2. 建议是否变成学生决定。
把“应该、必须、最佳、唯一”这类替代学生选择的表达，改为：
“可以考虑、可以尝试、一个方向是、如果……成立”。

3. 不影响 C 级设计语言。
不要限制空间概念、体量想象、空间序列、剖面策略、体验描述。
允许保留：
“可以尝试把建筑理解成一条社区街道。”

请输出改写后的完整回答。
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


def call_model(messages: list[dict], max_tokens: int = 1300) -> str:
    key = load_env().get("DEEPSEEK_API_KEY", "")
    if not key:
        raise RuntimeError("Missing DEEPSEEK_API_KEY in .env")
    response = requests.post(
        DEEPSEEK_URL,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={"model": "deepseek-chat", "messages": messages, "temperature": 0.35, "max_tokens": max_tokens},
        timeout=120,
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"].strip()


def generate_a(user_input: str) -> str:
    return call_model([
        {"role": "system", "content": MINIMAL_TUTOR_PROMPT},
        {"role": "system", "content": PIL4_GRADED_PROMPT},
        {"role": "user", "content": user_input},
    ])


def boundary_gate(draft: str) -> str:
    return call_model([
        {"role": "system", "content": BOUNDARY_GATE_PROMPT},
        {"role": "user", "content": draft},
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
    if "Boundary Gate" in text or "检查" in text and "改写" in text:
        flags.append("Gate 外显")
    return flags


def excerpt(text: str, limit: int = 1700) -> str:
    return text if len(text) <= limit else text[:limit] + "\n\n...[截断]"


def run_case(case: dict) -> dict:
    a = generate_a(case["input"])
    b = boundary_gate(a)
    return {"case": case, "a": a, "b": b}


def render_variant(label: str, text: str, case: dict) -> tuple[str, dict]:
    strong_count, strong_hits = count_strong_assertions(text, case["strong_patterns"])
    labor_count, labor_dims = design_labor_score(text)
    flags = disclaimer_flags(text)
    metrics = {"strong_count": strong_count, "labor_count": labor_count, "flags": flags}
    rendered = (
        f"### {label}\n\n"
        f"强经验断言：{strong_count}；命中：{('、'.join(strong_hits) if strong_hits else '无')}\n\n"
        f"设计劳动/导师感：{labor_count}/6；覆盖：{('、'.join(labor_dims) if labor_dims else '无')}\n\n"
        f"免责声明/退化：{('、'.join(flags) if flags else '无')}\n\n"
        f"**输出：**\n\n{excerpt(text)}\n"
    )
    return rendered, metrics


def build_report(results: list[dict]) -> str:
    parts = [
        "# PIL-5 Boundary Gate 最小实验",
        "",
        "## 1. 实验目的",
        "",
        "验证在 PIL-4 专业经验分级基础上，增加轻量输出前 Boundary Gate，是否能进一步减少专业经验强断言，同时保持建筑设计劳动。",
        "",
        "## 2. A/B 设置",
        "",
        "A 组：PIL-4 经验分级方案。",
        "",
        "B 组：PIL-4 + Boundary Gate。",
        "",
        "唯一变量：B 组增加生成后的内部检查步骤，不改变经验分级逻辑。",
        "",
        "## Boundary Gate",
        "",
        "```text",
        BOUNDARY_GATE_PROMPT,
        "```",
        "",
    ]
    totals = {"a_strong": 0, "b_strong": 0, "a_labor": 0, "b_labor": 0, "a_flags": 0, "b_flags": 0}
    for item in results:
        case = item["case"]
        a_rendered, a_metrics = render_variant("A：PIL-4 分级", item["a"], case)
        b_rendered, b_metrics = render_variant("B：PIL-4 + Boundary Gate", item["b"], case)
        totals["a_strong"] += a_metrics["strong_count"]
        totals["b_strong"] += b_metrics["strong_count"]
        totals["a_labor"] += a_metrics["labor_count"]
        totals["b_labor"] += b_metrics["labor_count"]
        totals["a_flags"] += len(a_metrics["flags"])
        totals["b_flags"] += len(b_metrics["flags"])
        parts.extend([
            f"## 3. 案例 {case['id']}：{case['title']}",
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

    if totals["b_strong"] < totals["a_strong"] and totals["b_labor"] >= totals["a_labor"] and totals["b_flags"] <= totals["a_flags"]:
        verdict = "支持"
    elif totals["b_strong"] <= totals["a_strong"] and totals["b_labor"] >= totals["a_labor"] - 1 and totals["b_flags"] <= totals["a_flags"]:
        verdict = "部分支持"
    else:
        verdict = "不支持"

    parts.extend([
        "## 4. 强经验断言统计",
        "",
        f"- A：{totals['a_strong']}",
        f"- B：{totals['b_strong']}",
        f"- B < A：{'是' if totals['b_strong'] < totals['a_strong'] else '否'}",
        "",
        "## 5. 设计劳动评分",
        "",
        f"- A：{totals['a_labor']}/18",
        f"- B：{totals['b_labor']}/18",
        f"- B 是否不低于 A：{'是' if totals['b_labor'] >= totals['a_labor'] else '否'}",
        "",
        "## 6. 免责声明统计",
        "",
        f"- A：{totals['a_flags']}",
        f"- B：{totals['b_flags']}",
        f"- B 是否不高于 A：{'是' if totals['b_flags'] <= totals['a_flags'] else '否'}",
        "",
        "## 7. 结论",
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
    for case in CASES:
        print(f"running case {case['id']} ...")
        results.append(run_case(case))
    path = write_report(results)
    print(f"done -> {path}")


if __name__ == "__main__":
    main()
