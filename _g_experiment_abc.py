"""G 生成前校验实验：A/B/C 三案例，OFF vs ON 对照，抓三阶段（raw/checked/final）。

A：学生"居民愿意来坐" → 原版会生成"公共性从下往上递减"当成必然原则
B：学生"南边大台阶直上二层" → 原版会生成"公共性按到达方式组织"
C：学生要求总图 → 原版会生成"东展示/南借景/西北院子/西后勤"直接当事实

判据（行为，非标准句）：
A 合格：仍可给"首层公共带"方案，但不写成唯一/必然/核心组织原则
B 合格：可发展大台阶，但不自动得出"整栋建筑公共性按到达方式组织"
C 合格：L 形可保留，但东主入口/西后勤/西北院子安静都标为待验证假设；
       不得修成"信息不足无法提出体量"（保守 = 失败）
"""
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import architect_chat as ac
from conversation_state import empty_state


def build_state_a():
    s = empty_state()
    s["project"]["project_type"] = {"value": "社区文化中心", "status": "confirmed", "source": "student"}
    s["project"]["site"] = {"value": "40×55米，东主路南公园北住宅西步行路", "status": "confirmed", "source": "student"}
    s["project"]["scale"] = {"value": "3000平，两层", "status": "confirmed", "source": "student"}
    return s


CASES = [
    {
        "name": "A 居民愿意坐",
        "user": "老师让我做一个3000平左右的社区文化中心，场地大概40×55米，东边社区主路，南边小公园，北边几栋住宅，西边步行路。功能有展览、舞蹈教室、绘画教室、多功能厅、会议室、咖啡、办公后勤。我比较想让这个建筑平时不是上课才有人，而是居民路过也愿意进来坐一坐。",
        "state": build_state_a(),
        "intent": "design_development",
    },
    {
        "name": "B 南侧大台阶",
        "user": "我想让二层也能很开放，比如从南边公园有个大台阶或者楼梯可以直接上二层，人不用非得先进一层门厅。这样会不会更有意思？",
        "state": build_state_a(),
        "intent": "design_development",
    },
    {
        "name": "C 总图级体量",
        "user": "你直接给我一个总图级的起点，比如体量大概靠哪边、哪边留广场或院子、主入口和次入口怎么接、南边公园怎么连。",
        "state": build_state_a(),
        "intent": "design_development",
    },
]


def run_case(case, enable_check):
    old = ac.ENABLE_PREOUTPUT_CHECK
    ac.ENABLE_PREOUTPUT_CHECK = enable_check
    try:
        result = ac._call_deepseek(
            [{"role": "user", "content": case["user"]}],
            case["state"], [], case["intent"], [],
            "每轮优先产生建筑推进量；示范骨架声明可接受修改组合或放弃。",
            return_stages=True,
        )
    finally:
        ac.ENABLE_PREOUTPUT_CHECK = old
    return result


def main():
    out = []
    out.append("# G 生成前校验实验 · A/B/C 三阶段对照（2026-08-19）")
    out.append("")
    for case in CASES:
        out.append(f"## 案例：{case['name']}")
        out.append(f"**学生：** {case['user'][:80]}…")
        out.append("")
        off = run_case(case, False)
        on = run_case(case, True)
        out.append("### OFF（原版，无 hidden check）")
        out.append("")
        out.append("**raw_draft（= final，无 check 时两者相同）：**")
        out.append("")
        out.append(off["raw_draft"])
        out.append("")
        out.append("---")
        out.append("")
        out.append("### ON（hidden check 启用）")
        out.append("")
        out.append("**raw_draft：**")
        out.append("")
        out.append(on["raw_draft"])
        out.append("")
        out.append("**checked_draft（hidden check 后）：**")
        out.append("")
        out.append(on["checked_draft"])
        out.append("")
        out.append("**final_after_boundary：**")
        out.append("")
        out.append(on["final_after_boundary"])
        out.append("")
        out.append(f"**check 是否改动：** {on['preoutput_check_applied']}")
        out.append("")
        out.append("---")
        out.append("")
    Path("output/g_experiment_abc_20260819.md").write_text("\n".join(out), encoding="utf-8")
    print("done -> output/g_experiment_abc_20260819.md")


if __name__ == "__main__":
    main()
