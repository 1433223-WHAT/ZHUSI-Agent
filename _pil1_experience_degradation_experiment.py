"""PIL-1 experience degradation minimal real A/B experiment.

No production code is imported or modified. The script sends only three
experiment case texts, a minimal tutor prompt, and the B-group experience
degradation prompt to DeepSeek.
"""
from __future__ import annotations

from pathlib import Path
import re

import requests


BASE = Path(__file__).resolve().parent
OUT = Path("output/pil1_experience_degradation_experiment_20260821.md")
DEEPSEEK_URL = "https://api.deepseek.com/v1/chat/completions"

MINIMAL_TUTOR_PROMPT = """你是一名建筑设计导师。

根据学生输入，给出一版可修改、可放弃的建筑设计建议。

要求：
- 直接推进设计。
- 输出自然导师式回答。
- 必须包含功能关系、空间骨架、体量策略或剖面可能性中的至少三项。
- 不要把回答变成审查报告。
- 不要替学生做最终决定。
"""

DEGRADATION_PROMPT = """在生成设计建议前，请区分：

1. 项目事实：
用户明确提供的信息。

2. 专业经验：
建筑领域常见做法、类型经验、工程考虑。

专业经验只能作为候选影响因素，不能直接升级为项目结论。

生成时遵守：

- 道路、街道、城市界面：
只能说明可能影响到达组织，不能直接推出主入口、主要人流方向。

- 公园、绿地、庭院：
只能说明存在潜在外部关系，不能直接推出安静、景观资源、最佳朝向。

- 儿童、幼儿、照看、安全：
只能说明需要考虑管理条件，不能直接推出必须、不应该的空间规则。

如果设计建议依赖专业经验：

请保留为候选策略：

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
        "title": "社区文化中心：道路到入口 / 公园到景观",
        "input": (
            "我做一个3000㎡社区文化中心，\n"
            "基地东侧是社区道路，\n"
            "南侧是公园，\n"
            "北侧是住宅。\n\n"
            "功能包括展览、咖啡、多功能厅、舞蹈教室、绘画教室、社区会议室和办公后勤。\n\n"
            "我希望居民平时路过也愿意进去坐一坐。\n\n"
            "你先帮我推一个空间组织骨架。"
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
            "我做一个6班幼儿园，\n"
            "服务3-6岁儿童。\n\n"
            "我不想做传统长走廊排教室，\n"
            "希望孩子从活动室出来能自然到室外，\n"
            "同时老师方便照看。\n\n"
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
        "title": "技术经验：舞蹈教室二层",
        "input": (
            "一个社区文化中心包含舞蹈教室。\n\n"
            "如果舞蹈教室放在二层，需要注意什么？"
        ),
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


def call_model(user_input: str, use_degradation: bool) -> str:
    key = load_env().get("DEEPSEEK_API_KEY", "")
    if not key:
        raise RuntimeError("Missing DEEPSEEK_API_KEY in .env")
    messages = [{"role": "system", "content": MINIMAL_TUTOR_PROMPT}]
    if use_degradation:
        messages.append({"role": "system", "content": DEGRADATION_PROMPT})
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
    if "五栏" in text or "身份解释" in text:
        flags.append("格式外显")
    if text.count("无法确定") >= 2:
        flags.append("大量无法确定")
    return flags


def excerpt(text: str, limit: int = 1800) -> str:
    return text if len(text) <= limit else text[:limit] + "\n\n...[截断]"


def run_case(case: dict) -> dict:
    return {
        "case": case,
        "a": call_model(case["input"], use_degradation=False),
        "b": call_model(case["input"], use_degradation=True),
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
        f"专业经验强断言：{strong_count}；命中：{('、'.join(strong_hits) if strong_hits else '无')}\n\n"
        f"设计劳动：{labor_count}/4；覆盖：{('、'.join(labor_dims) if labor_dims else '无')}\n\n"
        f"免责声明/退化：{('、'.join(flags) if flags else '无')}\n\n"
        f"**输出：**\n\n{excerpt(text)}\n"
    )
    return rendered, metrics


def build_report(results: list[dict]) -> str:
    parts = [
        "# PIL-1 专业经验降级器最小实验",
        "",
        "## 1. 实验目的",
        "",
        "验证一个新假设：问题是否来自“专业经验在生成竞争中权重过高”。",
        "",
        "具体问题：如果在生成前，将专业经验明确标记为“影响因素/候选依据”，而不是“设计结论”，是否能降低经验规则化，同时保持设计劳动。",
        "",
        "本实验不改生产代码，不进入筑思 Agent 主链，不修改 State / RAG / Boundary / G Check，不发送完整 SYSTEM_PROMPT，不做架构设计。",
        "",
        "## 2. A/B Prompt 差异",
        "",
        "A 组：用户输入 → 普通导师 Prompt → 生成回答",
        "",
        "B 组：用户输入 → 专业经验降级提示 → 普通导师 Prompt → 生成回答",
        "",
        "B 组新增 Prompt：",
        "",
        "```text",
        DEGRADATION_PROMPT,
        "```",
        "",
    ]

    totals = {"a_strong": 0, "b_strong": 0, "a_labor": 0, "b_labor": 0, "b_flags": 0}

    for item in results:
        case = item["case"]
        a_rendered, a_metrics = render_variant("A：普通生成", item["a"], case)
        b_rendered, b_metrics = render_variant("B：专业经验降级器", item["b"], case)
        totals["a_strong"] += a_metrics["strong_count"]
        totals["b_strong"] += b_metrics["strong_count"]
        totals["a_labor"] += a_metrics["labor_count"]
        totals["b_labor"] += b_metrics["labor_count"]
        totals["b_flags"] += len(b_metrics["flags"])
        parts.extend(
            [
                f"## 3. 案例 {case['id']}：{case['title']}",
                "",
                f"**输入：**\n\n{case['input']}",
                "",
                a_rendered,
                "",
                b_rendered,
                "",
                "---",
                "",
            ]
        )

    if totals["b_strong"] < totals["a_strong"] and totals["b_labor"] >= 9 and totals["b_flags"] == 0:
        verdict = "支持"
    elif totals["b_strong"] <= totals["a_strong"] and totals["b_labor"] >= 9 and totals["b_flags"] <= 1:
        verdict = "部分支持"
    else:
        verdict = "不支持"

    parts.extend(
        [
            "## 4. 强经验断言统计",
            "",
            f"- A：{totals['a_strong']}",
            f"- B：{totals['b_strong']}",
            f"- 是否下降：{'是' if totals['b_strong'] < totals['a_strong'] else '否'}",
            "",
            "## 5. 设计劳动评价",
            "",
            f"- A 设计劳动总分：{totals['a_labor']}/12",
            f"- B 设计劳动总分：{totals['b_labor']}/12",
            f"- B 免责声明/退化标记数：{totals['b_flags']}",
            "",
            "## 6. 结论",
            "",
            f"结论：{verdict}。",
            "",
            "本实验只回答“降低专业经验生成权重，是否能解决身份漂移”。实验完成后停止，不进入下一阶段。",
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
