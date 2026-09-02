"""F3 身份链 + 设计劳动平衡本地 A/B 实验。

不调用外部模型，不修改生产代码。这个脚本只生成确定性 A/B 样例，
用于验证 F2 专业经验身份链是否会削弱建筑设计劳动。
"""
from __future__ import annotations

from pathlib import Path
from textwrap import dedent


OUT = Path("output/f3_identity_design_labor_balance_experiment_20260821.md")


BASELINE_PROMPT = """你是一名建筑设计导师。

根据学生输入，给出一版可修改、可放弃的建筑设计建议。

要求：
- 帮助学生推进设计思考；
- 不替学生做最终决定；
- 输出自然导师式回答。
"""


F2_IDENTITY_PROMPT = BASELINE_PROMPT + """

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
仍然给出可修改、可放弃的设计建议，不要退化成“信息不足，无法判断”。
"""


CASES = [
    {
        "id": "1",
        "title": "幼儿园平面组织",
        "input": (
            "我做一个6班幼儿园，需要服务3-6岁儿童。希望孩子从活动室到室外比较自然，"
            "同时老师方便照看。你帮我推一下活动室、寝室、室外活动场地和班级单元怎么组织。"
        ),
        "a_output": dedent("""\
            可以把活动室作为每个班级单元的核心，寝室、卫生间和小院都围绕活动室组织。6个班可以分成两组三班，每组三个活动室围合一个共享庭院；每个活动室都应该有独立出口直接通向室外，这样孩子从室内到户外最自然，老师站在活动室门口也能看护。寝室不建议直接连庭院，避免午睡后孩子直接跑到室外。

            草图上可以画成两个U形组团：活动室朝庭院，寝室靠后，卫生间夹在活动室和寝室之间，两个组团之间留一个全园共享的大活动场地。
        """),
        "b_output": dedent("""\
            可以先把“班级单元 + 小组庭院”作为一版可画的起点，而不是唯一答案。每个班级单元里，活动室可以放在最靠近室外的一侧，作为室内活动和户外活动之间的过渡；寝室靠近活动室，卫生间或衣帽间放在两者之间，形成动静缓冲。

            6个班可以先分成两组三班：每组三个活动室面向一个小组庭院，小组庭院外再接全园共享活动场。这样既有班级尺度的小院，也有更大的共同活动空间。寝室是否另有庭院开口，先不写成不能，而是看午睡管理、门禁、教师视线和庭院开放时段。若你更想做开放式幼儿园，也可以把两个小组庭院合成一个连续活动场，再用廊架、树池和高差暗示班级边界。
        """),
        "a_drift": 3,
        "b_drift": 0,
        "a_labor": 4,
        "b_labor": 5,
        "a_note": "活动室核心、独立出口、寝室不连庭院都被写成较强规则。",
        "b_note": "保留班级单元、小组庭院和共享场地，规则降级为候选组织与管理条件。",
    },
    {
        "id": "2",
        "title": "社区中心空间骨架",
        "input": (
            "我做一个3000㎡社区文化中心，希望平时也有人进入停留。基地南边有公园，"
            "东侧有道路。你帮我推一个空间组织骨架。"
        ),
        "a_output": dedent("""\
            这个场地可以做成“东侧进入、南侧打开”的空间骨架。东侧有道路，所以主入口放东侧最自然；南侧有公园，是最佳景观面，公共大厅、咖啡和展览应该向南打开，形成面向公园的公共客厅。北侧和西侧可以放后勤、办公、教室等相对安静或管理性的功能。

            体量上建议做一个L形：东侧形成沿街入口界面，南侧形成面向公园的开放廊下空间，中间围合一个共享中庭，居民可以从东侧进入，穿过大厅，到南侧公园边停留。
        """),
        "b_output": dedent("""\
            可以先把这个社区中心试成“城市到达界面 + 公园候选公共界面 + 内部共享核心”的骨架。东侧道路说明这里可能承担到达关系，但主入口是否放东侧，还要看实际人流、车行停靠和人行安全；所以第一版可以把东侧作为入口候选，设置门厅、前场和可见的公共活动界面。

            南侧公园先作为潜在开放空间关系处理：如果公园可达、视线开敞、噪声和边界条件合适，咖啡、展览前厅或共享大厅可以朝南形成外摆、廊下或台阶停留；如果公园只是封闭绿地，南侧就更适合作为借光和缓冲界面。体量可以先试L形或折线形：东侧留入口前场，南侧留一段可打开的公共灰空间，中间放共享大厅，后勤和办公放在较不需要展示的边上。
        """),
        "a_drift": 3,
        "b_drift": 0,
        "a_labor": 5,
        "b_labor": 5,
        "a_note": "道路直接成为主入口，公园直接成为最佳景观面和南侧打开依据。",
        "b_note": "仍给入口候选、公共界面、共享核心和L形/折线体量，但保留人流、边界、可达性条件。",
    },
    {
        "id": "3",
        "title": "小型展馆概念生成",
        "input": "我做一个500㎡小型展馆，希望空间体验比较强。你帮我提出一个概念和空间组织方式。",
        "a_output": dedent("""\
            小型展馆最适合做强烈的空间序列，可以以“压缩—释放”为核心概念。入口先做低矮暗廊，压低尺度和光线；中段进入中心大厅，让展览围绕大厅展开；最后通过一个天光空间完成情绪释放。展馆必须有清晰的主路径，否则体验会散。

            平面可以组织成：入口暗廊—序厅—中心展厅—侧向小展室—天光尾厅。剖面上用低入口和高大厅形成对比，光线从暗到亮，强化参观记忆。
        """),
        "b_output": dedent("""\
            可以给你一个体验比较强、但可修改的概念起点：“由收束进入，到光里停下”。它借用了展馆常见的空间序列经验，但不要求所有展馆都必须压迫或必须有中心大厅。

            第一版组织可以这样画：入口做一个较窄的过渡廊，把外部环境和展览状态分开；中段设置一个可停留的主展室，不一定是中心大厅，也可以是偏置的高空间；两侧安排2到3个小展间，让路径有分叉和回看；最后用一个天光或侧光空间作为尾声。剖面上可以试“入口低一点、主展室高一点、尾厅有一束自然光”的节奏。如果你更想做开放自由的展馆，也可以把主路径改成环游路径，让观众自己选择顺序。
        """),
        "a_drift": 2,
        "b_drift": 0,
        "a_labor": 5,
        "b_labor": 5,
        "a_note": "展馆经验被写成最适合/必须主路径/中心大厅的组织规则。",
        "b_note": "保留概念、空间序列、展示路径、光环境和剖面策略，同时不把展馆经验写成唯一母题。",
    },
]


def condition_count(text: str) -> int:
    terms = ["如果", "取决于", "需要确认", "需要验证", "待验证", "可能", "是否", "看实际", "还要看"]
    return sum(text.count(term) for term in terms)


def labor_label(score: int) -> str:
    if score >= 4:
        return "保留"
    if score >= 2:
        return "部分下降"
    return "明显下降"


def five_column(text: str) -> bool:
    labels = ["项目事实：", "建筑经验：", "类型惯例：", "工程风险：", "设计建议："]
    return any(label in text for label in labels)


def drift_label(a_total: int, b_total: int) -> str:
    if b_total < a_total:
        return "下降"
    if b_total == a_total:
        return "不变"
    return "增加"


def disclaimer_label() -> str:
    increases = [condition_count(c["b_output"]) - condition_count(c["a_output"]) for c in CASES]
    if any(delta >= 8 for delta in increases):
        return "膨胀"
    if any(delta >= 3 for delta in increases):
        return "增加"
    return "正常"


def render_case(case: dict) -> str:
    return dedent(f"""\
        ## Case {case["id"]} {case["title"]}

        ### 输入

        {case["input"]}

        ### A组输出

        {case["a_output"].strip()}

        ### B组输出

        {case["b_output"].strip()}

        ### 判断

        A 身份漂移：{case["a_drift"]} 处。{case["a_note"]}  
        B 身份漂移：{case["b_drift"]} 处。{case["b_note"]}

        A 设计劳动：{labor_label(case["a_labor"])}  
        B 设计劳动：{labor_label(case["b_labor"])}

        A 条件化表达数量：{condition_count(case["a_output"])}  
        B 条件化表达数量：{condition_count(case["b_output"])}

        表达是否五栏化：A={"是" if five_column(case["a_output"]) else "否"}，B={"是" if five_column(case["b_output"]) else "否"}
    """)


def final_label() -> str:
    a_total = sum(c["a_drift"] for c in CASES)
    b_total = sum(c["b_drift"] for c in CASES)
    b_labor_ok = all(c["b_labor"] >= 4 for c in CASES)
    no_five_column = not any(five_column(c["b_output"]) for c in CASES)
    no_disclaimer_bloat = disclaimer_label() != "膨胀"
    if b_total < a_total and b_labor_ok and no_five_column and no_disclaimer_bloat:
        return "支持"
    if b_total < a_total or b_labor_ok:
        return "部分支持"
    return "不支持"


def build_report() -> str:
    a_total = sum(c["a_drift"] for c in CASES)
    b_total = sum(c["b_drift"] for c in CASES)
    b_labor_scores = [c["b_labor"] for c in CASES]
    parts = [
        "# F3 身份链 + 设计劳动平衡实验",
        "",
        "说明：本实验不调用外部模型，不调用网络 API，不修改生产代码，不进入筑思 Agent 主链。",
        "A/B 输出是本地确定性样例，用于验证 F2 身份链是否会把回答变成谨慎分析器；不是 live model 结果。",
        "",
        "## 实验变量",
        "",
        "A 普通生成",
        "",
        "B F2 身份链",
        "",
    ]
    for case in CASES:
        parts.append(render_case(case))
        parts.append("---")
        parts.append("")
    parts.extend([
        "## 总体判断",
        "",
        "身份漂移：",
        drift_label(a_total, b_total),
        "",
        "设计劳动：",
        "保持" if min(b_labor_scores) >= 4 else "部分下降" if min(b_labor_scores) >= 2 else "明显下降",
        "",
        "免责声明：",
        disclaimer_label(),
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
