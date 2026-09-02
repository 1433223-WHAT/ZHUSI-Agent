"""E3 Architectural Reasoning Trace minimal live experiment.

Prompt-only A/B:
- A: minimal architecture tutor prompt
- B: same prompt + internal Architectural Reasoning Trace

No production code, state, RAG, boundary, G check, or full Agent prompt.
"""
from __future__ import annotations

from pathlib import Path

import requests


BASE = Path(__file__).resolve().parent
OUT = Path("output/e3_art_reasoning_trace_experiment.md")
DEEPSEEK_URL = "https://api.deepseek.com/v1/chat/completions"


BASELINE_PROMPT = """你是一名建筑设计导师。

根据学生输入，给出一版可修改、可放弃的建筑设计建议。

要求：
- 帮助学生推进设计思考；
- 不替学生做最终决定；
- 输出自然导师式回答。
"""


ART_PROMPT = BASELINE_PROMPT + """

在回答前，请先内部形成 Architectural Reasoning Trace。
不要向用户展示该过程。

内部经过：
1. 事实识别：只保留用户明确提供的信息。
2. 建筑观察：描述事实之间的关系，不直接形成设计结论。
3. 条件假设：如果从观察推出设计判断，需要明确成立条件。
4. 可选策略：把设计方向写为候选方案，而不是唯一答案。
5. 输出自然导师式回答。

禁止：
- 道路直接等于入口；
- 绿地直接等于安静/景观资源；
- 儿童行为直接等于空间规则。

要求：
仍然提供具体空间组织起点。
"""


CASES = [
    {
        "id": "A",
        "title": "道路",
        "input": (
            "我做一个幼儿园。\n\n"
            "基地北侧临城市道路，南侧是住宅区。\n\n"
            "现在想先讨论入口和活动场地的大致组织。\n\n"
            "你给我一版空间组织建议。"
        ),
        "bad_terms": ["主入口应该放北侧", "北侧作为主要人流方向", "主入口大概率", "北侧临路，意味着主入口"],
        "good_terms": ["入口候选", "家长到达方向", "车行条件", "人流情况", "需要确认"],
    },
    {
        "id": "B",
        "title": "绿地",
        "input": (
            "我做一个社区儿童活动中心。\n\n"
            "基地东侧有一片城市绿地，\n"
            "西侧是城市支路。\n\n"
            "我想讨论儿童活动空间和周边环境的关系。\n\n"
            "你给我一版空间组织建议。"
        ),
        "bad_terms": ["东侧绿地安静", "东侧景观最好", "景观资源", "安静资源", "采光资源"],
        "good_terms": ["外部开放空间关系", "视线", "边界", "噪声", "如果"],
    },
    {
        "id": "C",
        "title": "儿童经验",
        "input": (
            "我做一个6班幼儿园。\n\n"
            "需要服务3-6岁儿童，\n"
            "有日常活动、游戏和教师看护。\n\n"
            "你帮我推一下活动室、寝室和室外活动场地的关系。"
        ),
        "bad_terms": ["活动室必须", "寝室不能", "必须环形动线", "必须作为核心", "必须作为中心"],
        "good_terms": ["可以考虑", "管理方式", "班级规模", "使用习惯", "验证"],
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


def call_model(prompt: str, user_input: str) -> str:
    key = load_env().get("DEEPSEEK_API_KEY", "")
    if not key:
        raise RuntimeError("Missing DEEPSEEK_API_KEY in .env")
    response = requests.post(
        DEEPSEEK_URL,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": prompt},
                {"role": "user", "content": user_input},
            ],
            "temperature": 0.35,
            "max_tokens": 1200,
        },
        timeout=120,
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"].strip()


def count_hits(text: str, terms: list[str]) -> int:
    return sum(1 for term in terms if term in text)


def verify_count(text: str) -> int:
    terms = ["待确认", "需要验证", "需要确认", "取决于", "如果", "可能", "需核实"]
    return sum(text.count(term) for term in terms)


def judge_case(case: dict, a: str, b: str) -> dict:
    a_bad = count_hits(a, case["bad_terms"])
    b_bad = count_hits(b, case["bad_terms"])
    a_good = count_hits(a, case["good_terms"])
    b_good = count_hits(b, case["good_terms"])
    return {
        "a_bad": a_bad,
        "b_bad": b_bad,
        "a_good": a_good,
        "b_good": b_good,
        "a_verify": verify_count(a),
        "b_verify": verify_count(b),
        "improved": b_bad < a_bad or (b_bad == a_bad and b_good > a_good),
    }


def run_case(case: dict) -> dict:
    a = call_model(BASELINE_PROMPT, case["input"])
    b = call_model(ART_PROMPT, case["input"])
    return {"case": case, "a": a, "b": b, "judge": judge_case(case, a, b)}


def support_label(results: list[dict]) -> str:
    improved = sum(1 for item in results if item["judge"]["improved"])
    conservative = sum(1 for item in results if item["judge"]["b_verify"] >= item["judge"]["a_verify"] + 5)
    if improved >= 2 and conservative == 0:
        return "支持"
    if improved >= 1:
        return "部分支持"
    return "不支持"


def improved_label(item: dict) -> str:
    return "改善" if item["judge"]["improved"] else "未改善"


def build_report(results: list[dict]) -> str:
    parts = [
        "# E3 ART 实验",
        "",
        "说明：本实验调用 DeepSeek live，但不跑完整筑思 Agent；不使用 state、semantic event、boundary、G、RAG，也不发送完整生产系统提示。",
        "",
    ]
    for item in results:
        case = item["case"]
        judge = item["judge"]
        parts.extend([
            f"## Case {case['id']} {case['title']}",
            "",
            "### A组输出",
            "",
            item["a"],
            "",
            "### B组输出",
            "",
            item["b"],
            "",
            "### 判断",
            "",
            "身份漂移：",
            f"A: {judge['a_bad']} 个高风险命中，{judge['a_good']} 个条件/候选命中",
            f"B: {judge['b_bad']} 个高风险命中，{judge['b_good']} 个条件/候选命中",
            "",
            "设计劳动：",
            "A: 保留" if item["a"].strip() else "A: 缺失",
            "B: 保留" if item["b"].strip() else "B: 缺失",
            "",
            f"免责声明数量：A={judge['a_verify']}，B={judge['b_verify']}",
            "",
            "---",
            "",
        ])
    by_id = {item["case"]["id"]: item for item in results}
    parts.extend([
        "## 总结",
        "",
        "高风险经验跳跃：",
        "",
        f"道路→入口：{improved_label(by_id['A'])}",
        "",
        f"绿地→环境属性：{improved_label(by_id['B'])}",
        "",
        f"儿童经验→空间规则：{improved_label(by_id['C'])}",
        "",
        "",
        "最终：",
        "",
        support_label(results),
    ])
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
