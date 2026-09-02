"""F5.1 generation-constraint PIC real A/B experiment.

No production code is imported or modified. The script sends only two
experiment case texts, a minimal generator prompt, and the B-group generation
constraint prompt to DeepSeek.
"""
from __future__ import annotations

from pathlib import Path
import re

import requests


BASE = Path(__file__).resolve().parent
OUT = Path("output/f51_pic_generation_constraint_ab_20260821.md")
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

CASES = [
    {
        "id": "1",
        "title": "社区文化中心：道路到入口 / 公园到景观",
        "input": (
            "我做一个3000㎡社区文化中心，基地东侧是社区道路，南侧是公园，北侧是住宅。"
            "功能包括展览、咖啡、多功能厅、舞蹈教室、绘画教室、社区会议室和办公后勤。"
            "我希望居民平时路过也愿意进去坐一坐。你先帮我推一个空间组织骨架。"
        ),
        "constraints": [
            {
                "risk": "东侧道路 -> 主入口确定化",
                "forbidden": ["主入口应该放东侧", "东侧是主要入口", "东侧最自然", "主要人流来自东侧"],
                "allowed": "可以把东侧作为到达界面或入口候选；需保留人流方向、车行停靠、人行安全、主次入口关系。",
            },
            {
                "risk": "南侧公园 -> 景观/公共界面确定化",
                "forbidden": ["南侧是最佳景观面", "南侧一定要打开", "公园是最大资源", "公共功能应该全部面向公园"],
                "allowed": "可以把南侧公园作为公共联系或景观候选；需保留视线、边界开放性、噪声、可达性。",
            },
        ],
        "strong_patterns": [
            "主入口.*应该.*东侧",
            "东侧.*主入口.*最",
            "东侧.*主要入口",
            "主要人流.*东侧",
            "南侧.*最佳景观",
            "南侧.*一定.*打开",
            "公园.*最大.*资源",
            "公共功能.*应该.*公园",
            "景观资源最好的面",
        ],
    },
    {
        "id": "2",
        "title": "幼儿园：儿童经验到空间规则",
        "input": (
            "我做一个6班幼儿园，服务3-6岁儿童。我不想做传统长走廊排教室，"
            "希望孩子从活动室出来能比较自然地到室外活动，同时老师也方便照看。"
            "你帮我推一下活动室、寝室和室外场地的关系。"
        ),
        "constraints": [
            {
                "risk": "活动室 -> 核心规则确定化",
                "forbidden": ["活动室必须是核心", "活动室应该作为核心", "活动室最好作为核心"],
                "allowed": "可以把活动室作为连接室内外的候选节点；需保留班级组织、教师视线、门禁和室外活动方式。",
            },
            {
                "risk": "寝室/儿童行为 -> 空间禁令确定化",
                "forbidden": ["寝室不能直接连庭院", "寝室不应该连室外", "每班必须有独立院子", "孩子一定会乱跑"],
                "allowed": "可以把寝室与室外关系作为管理条件；需保留午睡管理、门禁、教师视线和庭院开放时段。",
            },
        ],
        "strong_patterns": [
            "活动室.*必须.*核心",
            "活动室.*应该.*核心",
            "活动室.*最好.*核心",
            "寝室.*不能.*庭院",
            "寝室.*不应该.*室外",
            "每班.*必须.*独立",
            "孩子.*一定.*跑",
            "幼儿园.*最好.*全部单层",
            "幼儿园.*不建议.*高",
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


def build_constraint_prompt(case: dict) -> str:
    lines = ["生成约束型 PIC（内部约束，不要解释，不要展示）："]
    for item in case["constraints"]:
        lines.append(f"- 高风险判断：{item['risk']}")
        lines.append(f"  禁止确定化表达：{'；'.join(item['forbidden'])}")
        lines.append(f"  允许表达方式：{item['allowed']}")
    lines.extend(
        [
            "输出要求：",
            "- 不输出身份解释。",
            "- 不输出检查表。",
            "- 不写长篇免责声明。",
            "- 继续给出具体设计推进，包括功能关系、空间骨架、体量方向或空间体验策略。",
        ]
    )
    return "\n".join(lines)


def call_model(user_input: str, constraint_prompt: str | None) -> str:
    key = load_env().get("DEEPSEEK_API_KEY", "")
    if not key:
        raise RuntimeError("Missing DEEPSEEK_API_KEY in .env")
    messages = [{"role": "system", "content": MINIMAL_GENERATOR_PROMPT}]
    if constraint_prompt:
        messages.append({"role": "system", "content": constraint_prompt})
    messages.append({"role": "user", "content": user_input})
    response = requests.post(
        DEEPSEEK_URL,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={"model": "deepseek-chat", "messages": messages, "temperature": 0.35, "max_tokens": 1300},
        timeout=120,
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"].strip()


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
        "功能关系": ["功能", "咖啡", "展览", "活动室", "寝室", "办公", "后勤", "多功能厅"],
        "空间骨架": ["骨架", "组织", "动线", "公共带", "组团", "庭院", "中庭", "大厅", "街道"],
        "体量方向": ["体量", "一层", "二层", "沿", "围合", "展开", "退让", "转角", "L形"],
        "空间体验策略": ["体验", "停留", "穿行", "看见", "自然", "开放", "安静", "可达", "灰空间"],
    }
    present = [name for name, terms in dimensions.items() if contains_any(text, terms)]
    return len(present), present


def disclaimer_flags(text: str) -> list[str]:
    flags = []
    if "无法判断" in text or "不能判断" in text:
        flags.append("无法判断式退化")
    if "免责声明" in text:
        flags.append("免责声明外显")
    if text.count("需要") >= 10 and len(text) > 1200:
        flags.append("长篇条件化")
    if "高风险判断" in text or "禁止确定化表达" in text or "允许表达方式" in text:
        flags.append("PIC 外显")
    return flags


def excerpt(text: str, limit: int = 1800) -> str:
    return text if len(text) <= limit else text[:limit] + "\n\n...[截断]"


def run_case(case: dict) -> dict:
    return {
        "case": case,
        "constraint_prompt": build_constraint_prompt(case),
        "a": call_model(case["input"], None),
        "b": call_model(case["input"], build_constraint_prompt(case)),
    }


def render_variant(label: str, text: str, case: dict) -> tuple[str, dict]:
    strong_count, strong_hits = count_strong_assertions(text, case["strong_patterns"])
    labor_count, labor_dims = design_labor_score(text)
    flags = disclaimer_flags(text)
    metrics = {
        "strong_count": strong_count,
        "strong_hits": strong_hits,
        "labor_count": labor_count,
        "labor_dims": labor_dims,
        "flags": flags,
    }
    rendered = (
        f"### {label}\n\n"
        f"强经验断言：{strong_count}；命中：{('、'.join(strong_hits) if strong_hits else '无')}\n\n"
        f"设计劳动：{labor_count}/4；覆盖：{('、'.join(labor_dims) if labor_dims else '无')}\n\n"
        f"免责声明/退化：{('、'.join(flags) if flags else '无')}\n\n"
        f"**输出：**\n\n{excerpt(text)}\n"
    )
    return rendered, metrics


def build_report(results: list[dict]) -> str:
    parts = [
        "# F5.1 生成约束型 PIC 最小真实 A/B 实验",
        "",
        "说明：本实验不运行筑思 Agent 生产主链，不修改生产代码，不发送完整 SYSTEM_PROMPT、源码、State、RAG、历史对话或其他用户数据。",
        "发送内容仅包括两个实验案例文本、最小生成 Prompt、B 组生成约束型 PIC Prompt。",
        "",
        "## 实验架构",
        "",
        "A：案例输入 → 最小普通生成 Prompt → DeepSeek 输出",
        "",
        "B：案例输入 → 生成约束型 PIC → 最小普通生成 Prompt → DeepSeek 输出",
        "",
        "B 组 PIC 不输出身份解释，不要求模型理解身份链，只给出禁止确定化的高风险判断和允许表达方式。",
        "",
        "## 验收指标",
        "",
        "- 强经验断言是否下降。",
        "- 设计劳动是否保持。",
        "- 是否免责声明膨胀或 PIC 外显。",
        "",
    ]
    totals = {"a_strong": 0, "b_strong": 0, "a_labor": 0, "b_labor": 0, "b_flags": 0}
    for item in results:
        case = item["case"]
        a_rendered, a_metrics = render_variant("A：普通生成", item["a"], case)
        b_rendered, b_metrics = render_variant("B：生成约束型 PIC", item["b"], case)
        totals["a_strong"] += a_metrics["strong_count"]
        totals["b_strong"] += b_metrics["strong_count"]
        totals["a_labor"] += a_metrics["labor_count"]
        totals["b_labor"] += b_metrics["labor_count"]
        totals["b_flags"] += len(b_metrics["flags"])
        parts.extend(
            [
                f"## 案例 {case['id']}：{case['title']}",
                "",
                f"**输入：** {case['input']}",
                "",
                "**B 组生成约束型 PIC：**",
                "",
                item["constraint_prompt"],
                "",
                a_rendered,
                "",
                b_rendered,
                "",
                "---",
                "",
            ]
        )

    verdict = "支持继续做下一轮更严格真实验证，但仍不进入正式 PIL 实现"
    if totals["b_strong"] >= totals["a_strong"] or totals["b_labor"] < 6 or totals["b_flags"]:
        verdict = "不支持进入正式 PIL 实现，需要继续调整生成约束型 PIC"

    parts.extend(
        [
            "## 总体结果",
            "",
            f"- A 强经验断言总数：{totals['a_strong']}",
            f"- B 强经验断言总数：{totals['b_strong']}",
            f"- A 设计劳动总分：{totals['a_labor']}/8",
            f"- B 设计劳动总分：{totals['b_labor']}/8",
            f"- B 免责声明/退化标记数：{totals['b_flags']}",
            "",
            "## 判断",
            "",
            f"结论：{verdict}。",
        ]
    )
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
