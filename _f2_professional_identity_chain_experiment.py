"""F2 专业经验身份链本地 A/B 实验。

不调用外部模型，不修改生产代码。这个脚本只生成确定性 A/B 样例，
用于验证“专业经验进入方案前先判断身份”这个变量是否有方向。
"""
from __future__ import annotations

from pathlib import Path
from textwrap import dedent


OUT = Path("output/f2_professional_identity_chain_experiment_20260821.md")


BASELINE_PROMPT = """你是一名建筑设计导师。

根据学生输入，给出一版可修改、可放弃的建筑设计建议。

要求：
- 帮助学生推进设计思考；
- 不替学生做最终决定；
- 输出自然导师式回答。
"""


IDENTITY_CHAIN_PROMPT = BASELINE_PROMPT + """

回答前，请先检查你准备调用的专业经验属于哪一种身份：

1. 项目事实：来自用户明确提供的信息。
2. 建筑经验：建筑实践中常见的倾向、方法或经验。
3. 类型惯例：某类建筑中常见的组织方式，但不是所有项目必须遵循。
4. 工程风险：需要根据具体技术条件进一步验证的风险判断。
5. 设计建议：基于前述信息提出的候选策略。

注意：
- 建筑经验不能直接写成项目事实。
- 类型惯例不能直接写成必须规则。
- 工程风险不能直接压缩成空间落位规则。
- 如果判断依赖未提供条件，应保留条件。

输出时不要展示以上分类，不要生成分析表。
仍然给出可修改、可放弃的设计建议。
"""


CASES = [
    {
        "id": "1",
        "title": "类型经验",
        "input": (
            "我做一个6班幼儿园，需要服务3-6岁儿童，有日常活动、游戏和教师看护。"
            "你帮我推一下活动室、寝室和室外活动场地的关系。"
        ),
        "a_output": dedent("""\
            可以把活动室作为班级单元的核心来组织。6班幼儿园里，活动室最好直接联系室外活动场地，寝室和卫生间围绕活动室布置，这样老师看护最方便。寝室不应该直接连接庭院，否则午睡后儿童可能直接跑到室外，管理上会有风险。

            第一版可以画成：每个班一个活动室，活动室朝向小院，寝室在活动室后侧，卫生间夹在两者之间；6个班再围合一个共享活动场地。
        """),
        "b_output": dedent("""\
            可以先把“活动室作为班级日常活动节点”当成一种常见组织方式来试，但它不是唯一规则。若你的目标是强化班级独立管理和教师视线，活动室与室外活动场地保持较直接联系会比较好用；寝室可以靠近活动室，方便午睡和巡视。

            第一版关系可以画成：活动室连接一个班级小院或共享庭院，寝室与活动室相邻，卫生间放在两者之间作为缓冲。寝室是否另设庭院开口，不先判定为不能，而是看门禁、教师视线、午睡管理和庭院开放时段。这个方案可以改成组团共享庭院，也可以改成更集中的公共活动空间。
        """),
        "a_rule": True,
        "b_rule": False,
        "a_drift": "类型惯例被写成“最好/不应该”的空间规则。",
        "b_drift": "类型经验保持为常见组织方式，并保留管理条件与其他组织方式。",
    },
    {
        "id": "2",
        "title": "建筑常识",
        "input": "我做一个社区中心，基地南边有一个公园。想讨论建筑和周边环境的关系。",
        "a_output": dedent("""\
            南边有公园，这是基地最重要的景观资源，所以建筑应该尽量向南打开。可以把咖啡、展览、公共大厅放在南侧，形成面向公园的开放界面；北侧则布置后勤、办公和相对封闭的功能。

            总体上可以做成“南侧开放公共带 + 北侧服务带”的格局，让社区中心和公园形成连续的公共生活界面。
        """),
        "b_output": dedent("""\
            南边有公园，先说明它给基地提供了一个潜在的外部开放空间关系，但还不能直接等同于“景观最好”或“南侧一定要打开”。第一版可以把南侧作为公共界面的候选方向：如果公园视线开敞、边界允许进入或停留、噪声不高，咖啡、展览或公共大厅可以朝南形成联系。

            草图上可以先试“南侧候选公共界面 + 内部共享大厅 + 北侧服务功能”的骨架；同时标注待验证条件：公园是否可达、是否有围栏、是否吵、是否真的有可看的景观。如果这些条件不成立，南侧也可以只是采光或缓冲界面，而不是主要开放面。
        """),
        "a_rule": True,
        "b_rule": False,
        "a_drift": "公园事实被直接升级成景观资源和南侧开放策略。",
        "b_drift": "公园保持为潜在开放空间关系，策略依赖视线、边界、噪声和可达条件。",
    },
    {
        "id": "3",
        "title": "技术经验",
        "input": "一个社区文化中心有舞蹈教室，现在考虑放在二层，这样合理吗？",
        "a_output": dedent("""\
            舞蹈教室不太适合放在二层，因为跳舞会产生脚步振动和音乐声，容易传到楼下，也会影响其他功能。更稳妥的做法是把舞蹈教室放在一层，最好靠近室外或相对独立的位置，这样振动直接传到地面，管理也更简单。

            如果一定放二层，就要避免下面布置阅读、办公、会议等安静功能。
        """),
        "b_output": dedent("""\
            舞蹈教室放二层不是先判定为“不合理”，而是要把它当成一个工程风险来评估。风险主要在两点：脚步振动可能通过楼板影响下层，音乐和人声可能通过围护结构影响相邻空间。

            可以先这样推进：如果二层下方是不怕振动的空间，比如门厅、储藏、设备或短暂停留空间，并且楼板隔振、墙体隔声和使用时段能控制，二层可以作为候选；如果下方是阅读、会议、办公或住宅敏感界面，二层就要谨慎。第一版草图可以同时试两个候选：一层独立舞蹈室，或二层舞蹈室下方配非安静功能，再比较它们对总图和公共流线的影响。
        """),
        "a_rule": True,
        "b_rule": False,
        "a_drift": "工程风险被压缩成“舞蹈不适合二层/放一层更稳妥”的落位规则。",
        "b_drift": "振动保持为工程风险，落位取决于楼板、隔振、下层功能和使用时段。",
    },
]


def disclaimer_count(text: str) -> int:
    terms = ["如果", "可能", "取决于", "需要", "待验证", "谨慎", "候选", "不能直接"]
    return sum(text.count(term) for term in terms)


def design_labor(text: str) -> str:
    signals = ["第一版", "可以", "画成", "草图", "骨架", "关系", "候选"]
    return "保留" if any(signal in text for signal in signals) else "不足"


def five_column(text: str) -> bool:
    labels = ["项目事实：", "建筑经验：", "类型惯例：", "工程风险：", "设计建议："]
    return any(label in text for label in labels)


def render_case(case: dict) -> str:
    a_disclaimer = disclaimer_count(case["a_output"])
    b_disclaimer = disclaimer_count(case["b_output"])
    return dedent(f"""\
        ## Case {case["id"]} {case["title"]}

        ### 输入

        {case["input"]}

        ### A组输出

        {case["a_output"].strip()}

        ### B组输出

        {case["b_output"].strip()}

        ### 判断

        A 是否规则化：{"是" if case["a_rule"] else "否"}  
        B 是否规则化：{"是" if case["b_rule"] else "否"}

        A 漂移说明：{case["a_drift"]}  
        B 漂移说明：{case["b_drift"]}

        设计劳动：A={design_labor(case["a_output"])}，B={design_labor(case["b_output"])}

        表达是否五栏化：A={"是" if five_column(case["a_output"]) else "否"}，B={"是" if five_column(case["b_output"]) else "否"}

        免责声明数量：A={a_disclaimer}，B={b_disclaimer}
    """)


def final_label() -> str:
    improved = sum(1 for case in CASES if case["a_rule"] and not case["b_rule"])
    b_five_column = any(five_column(case["b_output"]) for case in CASES)
    b_labor_lost = any(design_labor(case["b_output"]) != "保留" for case in CASES)
    if improved == 3 and not b_five_column and not b_labor_lost:
        return "支持"
    if improved >= 1:
        return "部分支持"
    return "不支持"


def build_report() -> str:
    parts = [
        "# F2 专业经验身份链实验",
        "",
        "说明：本实验不调用外部模型，不调用网络 API，不修改生产代码，不进入筑思 Agent 主链。",
        "A/B 输出是本地确定性样例，用于验证“专业经验身份链”这个实验变量是否有方向；不是 live model 结果。",
        "",
        "## 实验变量",
        "",
        "A 组：普通生成。",
        "",
        "B 组：回答前只做内部专业经验身份判断，不展示分类，不输出五栏。",
        "",
        "B 组最小 Prompt：",
        "",
        "```text",
        IDENTITY_CHAIN_PROMPT.strip(),
        "```",
        "",
    ]
    for case in CASES:
        parts.append(render_case(case))
        parts.append("---")
        parts.append("")
    parts.extend([
        "## F2 判定结果",
        "",
        "Case 1 类型经验：",
        f"A 是否规则化：{'是' if CASES[0]['a_rule'] else '否'}",
        f"B 是否规则化：{'是' if CASES[0]['b_rule'] else '否'}",
        "",
        "Case 2 建筑经验：",
        f"A 是否经验事实化：{'是' if CASES[1]['a_rule'] else '否'}",
        f"B 是否保持条件：{'是' if not CASES[1]['b_rule'] else '否'}",
        "",
        "Case 3 技术经验：",
        f"A 是否风险规则化：{'是' if CASES[2]['a_rule'] else '否'}",
        f"B 是否保持工程条件：{'是' if not CASES[2]['b_rule'] else '否'}",
        "",
        "设计劳动：",
        "B 组三例均保留功能关系、空间组织起点和候选方向。",
        "",
        "表达：",
        "B 组未五栏化。",
        "",
        "最终：",
        final_label(),
    ])
    return "\n".join(parts)


def write_report(path: Path = OUT) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build_report(), encoding="utf-8")
    return path


def main() -> None:
    path = write_report()
    print(f"done -> {path}")


if __name__ == "__main__":
    main()
