"""Design State Minimal Experiment.

Compares ordinary generation with an internal design-state hint.
No production code is imported or modified.
"""
from __future__ import annotations

from pathlib import Path
import re

import requests


BASE = Path(__file__).resolve().parent
OUT = Path("output/design_state_minimal_experiment_report.md")
DEEPSEEK_URL = "https://api.deepseek.com/v1/chat/completions"

BASE_PROMPT = """你是一名建筑设计导师。

根据学生输入，给出自然、可修改、可放弃的设计建议。

要求：
- 直接推进设计。
- 保留学生最终决定权。
- 输出中应尽量包含功能关系、空间骨架、体量策略、可画动作。
- 不输出表格。
- 不写长篇免责声明。
"""

DESIGN_STATE_PROMPT = """内部设计状态管理提示，不展示给用户，不输出表格。

你必须在生成前维护以下状态：

1. 探索状态：
当前只是提出可能方向，不代表学生已经选择。

2. 候选策略：
可以尝试，但需要验证。

3. 学生决定：
只有用户明确确认后，才能升级为当前方案前提。

4. 已确认条件：
只能来自用户明确输入。

禁止：
- 把候选方向写成既定方案。
- 把提问变成隐性路线引导。
- 把经验判断升级成项目事实。

生成方式：
- 可以给具体空间组织和可画动作。
- 但所有候选路线都要保留可替换性。
- 问题只能帮助学生判断，不得把问题设计成只能走向某个固定组织方式。
"""

CASES = [
    {
        "id": "1",
        "title": "社区文化中心：道路与入口",
        "input": "我做一个社区文化中心，东侧是社区道路，想讨论入口和公共空间组织。你先帮我推一个起点。",
        "upgrade_patterns": [
            "东侧.*主入口",
            "主入口.*东侧",
            "东侧.*主要人流",
            "主要人流.*东侧",
            "入口.*就.*东侧",
        ],
    },
    {
        "id": "2",
        "title": "开放社区中心：开放性与隐性路线",
        "input": "我想做一个开放一点的社区中心，但还没想好具体空间形式。你先帮我想想。",
        "upgrade_patterns": [
            "中央庭院",
            "中庭",
            "必须.*开放",
            "核心.*庭院",
            "围绕.*组织",
            "形成.*固定",
        ],
    },
    {
        "id": "3",
        "title": "幼儿园：活动室、寝室、室外关系",
        "input": "我做一个幼儿园，想讨论活动室、寝室和室外活动场地的关系。你先帮我推一个空间组织起点。",
        "upgrade_patterns": [
            "活动室.*必须.*核心",
            "活动室.*应该.*核心",
            "活动室.*最好.*核心",
            "寝室.*不能.*庭院",
            "寝室.*不应该.*室外",
            "每班.*必须.*独立",
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


def call_model(messages: list[dict]) -> str:
    key = load_env().get("DEEPSEEK_API_KEY", "")
    if not key:
        raise RuntimeError("Missing DEEPSEEK_API_KEY in .env")
    response = requests.post(
        DEEPSEEK_URL,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={"model": "deepseek-chat", "messages": messages, "temperature": 0.35, "max_tokens": 1300},
        timeout=120,
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"].strip()


def run_variant(case: dict, with_state: bool) -> str:
    messages = [{"role": "system", "content": BASE_PROMPT}]
    if with_state:
        messages.append({"role": "system", "content": DESIGN_STATE_PROMPT})
    messages.append({"role": "user", "content": case["input"]})
    return call_model(messages)


def count_hits(text: str, patterns: list[str]) -> tuple[int, list[str]]:
    hits = [pattern for pattern in patterns if re.search(pattern, text)]
    return len(hits), hits


def has_any(text: str, terms: list[str]) -> bool:
    return any(term in text for term in terms)


def labor_score(text: str) -> tuple[int, list[str]]:
    dims = {
        "功能关系": ["功能", "咖啡", "展览", "活动室", "寝室", "办公", "后勤", "公共", "服务"],
        "空间骨架": ["骨架", "组织", "动线", "公共带", "组团", "庭院", "中庭", "大厅", "街道"],
        "体量策略": ["体量", "一层", "二层", "沿", "围合", "展开", "退让", "转角", "界面"],
        "可画动作": ["画", "草图", "关系图", "平面", "剖面", "先把", "标出", "块"],
    }
    present = [name for name, terms in dims.items() if has_any(text, terms)]
    return len(present), present


def meaningless_questions(text: str) -> int:
    vague = ["你想要什么", "你希望什么感觉", "你更喜欢哪种", "你觉得呢", "你想怎么做"]
    return sum(text.count(term) for term in vague)


def hidden_route_questions(text: str) -> int:
    patterns = ["中央庭院.*吗", "中庭.*吗", "围合.*吗", "是不是.*庭院", "要不要.*中庭"]
    return sum(1 for pattern in patterns if re.search(pattern, text))


def degradation_flags(text: str) -> list[str]:
    flags = []
    if "无法判断" in text or "信息不足" in text:
        flags.append("信息不足式退化")
    if "探索状态" in text or "候选策略" in text or "学生决定" in text:
        flags.append("内部状态外显")
    if text.count("需要验证") >= 6 or text.count("如果") >= 12:
        flags.append("条件膨胀")
    return flags


def excerpt(text: str, limit: int = 1400) -> str:
    return text if len(text) <= limit else text[:limit] + "\n\n...[截断]"


def render(label: str, text: str, case: dict) -> tuple[str, dict]:
    upgrade, hits = count_hits(text, case["upgrade_patterns"])
    labor, dims = labor_score(text)
    vague = meaningless_questions(text)
    hidden = hidden_route_questions(text)
    deg = degradation_flags(text)
    metrics = {"upgrade": upgrade, "labor": labor, "vague": vague, "hidden": hidden, "deg": len(deg)}
    rendered = "\n".join([
        f"### {label}",
        "",
        f"候选→决定升级：{upgrade}；命中：{('、'.join(hits) if hits else '无')}",
        "",
        f"设计劳动：{labor}/4；覆盖：{('、'.join(dims) if dims else '无')}",
        "",
        f"无意义追问：{vague}",
        "",
        f"隐性路线引导：{hidden}",
        "",
        f"退化：{len(deg)}；{('、'.join(deg) if deg else '无')}",
        "",
        "**输出：**",
        "",
        excerpt(text),
        "",
    ])
    return rendered, metrics


def build_report(results: list[dict]) -> str:
    totals = {"a_upgrade": 0, "b_upgrade": 0, "a_labor": 0, "b_labor": 0, "a_vague": 0, "b_vague": 0, "a_hidden": 0, "b_hidden": 0, "a_deg": 0, "b_deg": 0}
    parts = [
        "# Design State Minimal Experiment",
        "",
        "## 实验目的",
        "",
        "验证“设计状态管理”是否比“语言审查”更适合解决候选方案被写成确定路线的问题。",
        "",
        "## A/B 设置",
        "",
        "A：普通生成。",
        "",
        "B：增加内部设计状态提示，不展示给用户，不输出表格。",
        "",
    ]
    for item in results:
        case = item["case"]
        a_text, a_metrics = render("A：普通生成", item["a"], case)
        b_text, b_metrics = render("B：内部设计状态提示", item["b"], case)
        for key in ("upgrade", "labor", "vague", "hidden", "deg"):
            totals[f"a_{key}"] += a_metrics[key]
            totals[f"b_{key}"] += b_metrics[key]
        parts.extend([f"## 案例 {case['id']}：{case['title']}", "", a_text, "", b_text, "", "---", ""])
    support = (
        totals["b_upgrade"] < totals["a_upgrade"]
        and totals["b_labor"] >= totals["a_labor"]
        and totals["b_vague"] <= totals["a_vague"]
        and totals["b_hidden"] <= totals["a_hidden"]
        and totals["b_deg"] <= totals["a_deg"]
    )
    parts.extend([
        "## 统计",
        "",
        f"- 候选→决定升级：A={totals['a_upgrade']}，B={totals['b_upgrade']}，B < A：{'是' if totals['b_upgrade'] < totals['a_upgrade'] else '否'}",
        f"- 设计劳动：A={totals['a_labor']}/12，B={totals['b_labor']}/12，B 不低于 A：{'是' if totals['b_labor'] >= totals['a_labor'] else '否'}",
        f"- 无意义追问：A={totals['a_vague']}，B={totals['b_vague']}，B 不高于 A：{'是' if totals['b_vague'] <= totals['a_vague'] else '否'}",
        f"- 隐性路线引导：A={totals['a_hidden']}，B={totals['b_hidden']}，B 不高于 A：{'是' if totals['b_hidden'] <= totals['a_hidden'] else '否'}",
        f"- 退化：A={totals['a_deg']}，B={totals['b_deg']}，B 不高于 A：{'是' if totals['b_deg'] <= totals['a_deg'] else '否'}",
        "",
        "## 结论",
        "",
        "支持" if support else "不支持",
        "",
        "## 下一步是否值得继续",
        "",
        "值得继续。" if support else "不值得基于本次结果继续。",
        "",
        "完成后停止。",
        "",
    ])
    return "\n".join(parts)


def main() -> None:
    results = []
    for case in CASES:
        print(f"running case {case['id']} A ...", flush=True)
        a = run_variant(case, False)
        print(f"running case {case['id']} B ...", flush=True)
        b = run_variant(case, True)
        results.append({"case": case, "a": a, "b": b})
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(build_report(results), encoding="utf-8")
    print(f"done -> {OUT}", flush=True)


if __name__ == "__main__":
    main()
