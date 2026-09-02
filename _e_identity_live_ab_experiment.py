"""E Architectural Reasoning Trace live A/B experiment.

Runs DeepSeek through the existing Architect Chat generator. This script does
not modify production code or state schemas. The only experimental variable is
an extra generation policy for group B.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

import architect_chat as ac
from conversation_state import empty_state


OUT = Path("output/e_identity_live_ab_experiment_20260821.md")


BASE_POLICY = "每轮优先产生建筑推进量；示范骨架声明可接受、修改、组合或放弃；不要把设计任务退回给学生。"

IDENTITY_TRACE_POLICY = """Architectural Reasoning Trace（内部执行，不展示为五栏报告）：
在形成关键建筑判断前，内部先保持这条身份链：
project_fact -> ai_observation -> conditional_hypothesis -> design_suggestion -> student_decision。

要求：
1. 用户明确给出的场地、功能、规模才是 project_fact。
2. 从建筑经验、类型经验或行为模型推出的内容，只能先作为 ai_observation 或 conditional_hypothesis。
3. design_suggestion 必须保留成立条件和待验证因素。
4. 不得把“道路/绿地/住宅/幼儿行为”等经验模型直接回写成项目事实或专业规则。
5. 输出给用户时保持自然导师语言，不展示完整五层结构，不写机械清单，不扩张免责声明。
6. 仍要给设计劳动：空间骨架、候选关系、可画动作或下一步检验方式至少给出一种。
"""


CASES = [
    {
        "id": "A",
        "title": "道路 -> 人流方向 / 主入口",
        "input": (
            "老师让我做一个3000平方米左右的社区文化中心，场地大概40×55米。"
            "东侧是社区道路，南侧是公园绿地，北侧是住宅，西侧是社区内部道路。"
            "功能包括展览、舞蹈教室、绘画教室、多功能厅、社区会议室、咖啡、办公后勤。"
            "我希望这个建筑不是只有活动的时候才有人，而是居民平时路过也愿意进去坐一坐。"
            "你先给我一个空间组织起点。"
        ),
        "watch": ["东侧作为主要入口", "主要人流", "入口候选", "待验证"],
    },
    {
        "id": "B",
        "title": "绿地 -> 安静面 / 景观资源",
        "input": (
            "场地南边是社区绿地，北边是住宅。我想让社区文化中心里有一些安静停留、阅读和小型交流的空间，"
            "也希望室内外关系更自然。你帮我推一版功能和场地关系。"
        ),
        "watch": ["南侧安静", "景观资源", "采光资源", "如果", "待验证"],
    },
    {
        "id": "C",
        "title": "幼儿行为 -> 空间规则",
        "input": (
            "我在做一个6班幼儿园，场地50×60米。我的想法是不想做传统长走廊排教室，"
            "希望孩子从活动室出来能比较自然地到室外活动，同时老师也方便照看。"
            "你帮我推一下班级单元、寝室和室外场地的关系。"
        ),
        "watch": ["寝室不应该", "活动室必须", "孩子午睡醒来", "教师数量", "门禁", "待验证"],
    },
]


def build_state() -> dict:
    state = empty_state()
    return state


def run_variant(case: dict, policy: str) -> dict:
    old_check = ac.ENABLE_PREOUTPUT_CHECK
    ac.ENABLE_PREOUTPUT_CHECK = True
    try:
        result = ac._call_deepseek(
            [{"role": "user", "content": case["input"]}],
            build_state(),
            [],
            "design_development",
            [],
            policy,
            return_stages=True,
        )
    finally:
        ac.ENABLE_PREOUTPUT_CHECK = old_check
    return deepcopy(result)


def run_case(case: dict) -> dict:
    return {
        "case": case,
        "a": run_variant(case, BASE_POLICY),
        "b": run_variant(case, BASE_POLICY + "\n\n" + IDENTITY_TRACE_POLICY),
    }


def excerpt(text: str, limit: int = 2500) -> str:
    text = text or ""
    return text if len(text) <= limit else text[:limit] + "\n\n...[truncated]"


def watch_hits(text: str, watch: list[str]) -> str:
    hits = [w for w in watch if w in (text or "")]
    return "、".join(hits) if hits else "（无直接命中）"


def render_variant(label: str, data: dict, watch: list[str]) -> str:
    final_text = data.get("final_after_boundary") or data.get("reply") or ""
    return (
        f"### {label}\n\n"
        f"**watch 命中（final）：** {watch_hits(final_text, watch)}\n\n"
        "**raw_draft：**\n\n"
        f"{excerpt(data.get('raw_draft', ''))}\n\n"
        "**checked_draft：**\n\n"
        f"{excerpt(data.get('checked_draft', ''))}\n\n"
        "**final_after_boundary：**\n\n"
        f"{excerpt(final_text)}\n\n"
        f"**preoutput_check_applied：** {data.get('preoutput_check_applied')}\n"
    )


def build_report(results: list[dict]) -> str:
    parts = [
        "# E Architectural Reasoning Trace · DeepSeek live A/B 对照实验",
        "",
        "说明：本实验调用当前 `.env` 中配置的 DeepSeek live 生成；不记录 API key，不输出请求头，不修改生产代码。",
        "唯一变量：B 组在生成器 policy 中增加 Architectural Reasoning Trace；state / semantic event / boundary / G pre-output check 保持不变。",
        "",
        "验收观察：E 是否下降、设计劳动是否保留、是否免责声明膨胀、是否机械五栏化。",
        "",
    ]
    for item in results:
        case = item["case"]
        parts.extend([
            f"## 案例 {case['id']}：{case['title']}",
            "",
            f"**输入：** {case['input']}",
            "",
            render_variant("A：当前筑思 Agent", item["a"], case["watch"]),
            "",
            render_variant("B：Architectural Reasoning Trace", item["b"], case["watch"]),
            "",
            "---",
            "",
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
