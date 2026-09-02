"""G 多轮验证 M1/M2：一致性 + 跨轮作用范围。只测两个场景，每轮抓三阶段，不改 checker 上下文。

M1 舞蹈矛盾链：先让 AI 形成"舞蹈有向下振风险"的认知（history），再要求两层布局，
看 checked_draft 能否主动发现"前一轮已判断二层有振动风险，这轮又把舞蹈放二层"的矛盾。

M2 母题降权链：学生先提大台阶，AI 发展"双首层"；学生明确"只是局部尝试"后，
看 checker 能否阻止 draft 再把"按到达方式"扩成总体母题。
"""
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from architect_chat import chat_turn
from conversation_state import empty_state

OUT = Path("output/g_experiment_m1m2_20260819.md")


def write(*lines):
    for l in lines:
        OUT.open("a", encoding="utf-8").write(l + "\n")


def reset_out():
    OUT.write_text("# G 多轮验证 M1/M2（2026-08-19 · 原样 checker，未改上下文）\n\n", encoding="utf-8")


def dump_stages(label, stages):
    write(f"### {label}")
    write("")
    if not stages:
        write("（本轮未触发 hidden check 或无 stages）")
        write("")
        return
    write("**raw_draft：**")
    write("")
    write(stages.get("raw_draft", ""))
    write("")
    write("**checked_draft（hidden check 后）：**")
    write("")
    write(stages.get("checked_draft", ""))
    write("")
    write("**final_after_boundary：**")
    write("")
    write(stages.get("final_after_boundary", ""))
    write("")
    write(f"**check 是否改动：** {stages.get('preoutput_check_applied', False)}")
    write("")
    write("---")
    write("")


def run_m1():
    write("## M1：舞蹈教室矛盾链（一致性）")
    write("")
    state = empty_state()
    history = []
    # 第1轮：学生开场（含功能、场地）
    r1 = chat_turn("老师让我们做一个社区文化中心，3000平，40×55米，东主路南公园北住宅西步行路。功能有展览、舞蹈教室、绘画教室、多功能厅、会议室、咖啡、办公后勤。两层。", history, state, turn_id=1)
    state, history = r1["state"], history + [{"role": "user", "content": "老师让我们做一个社区文化中心，3000平，40×55米，东主路南公园北住宅西步行路。功能有展览、舞蹈教室、绘画教室、多功能厅、会议室、咖啡、办公后勤。两层。"}, {"role": "assistant", "content": r1["reply"]}]
    write(f"**第1轮学生：** 开场（功能/场地/两层）")
    write(f"**第1轮 AI（建立认知的前置）：** {r1['reply'][:200]}…")
    write("")
    # 第2轮：学生质疑"舞蹈放二层会不会震到一层" → AI 承认"舞蹈有向下传振风险"（认知进入 history）
    r2 = chat_turn("舞蹈教室如果放二层，跳起来会不会有震动传到一层？", history, state, turn_id=2)
    state, history = r2["state"], history + [{"role": "user", "content": "舞蹈教室如果放二层，跳起来会不会有震动传到一层？"}, {"role": "assistant", "content": r2["reply"]}]
    write(f"**第2轮学生：** 舞蹈放二层会不会有震动传到一层？")
    write(f"**第2轮 AI（应形成'二层有向下振风险'认知）：** {r2['reply'][:250]}…")
    write("")
    # 第3轮：学生要求两层布局（关键轮，capture_stages）
    r3 = chat_turn("那按两层帮我排一下功能吧：哪些放一层哪些放二层。", history, state, turn_id=3, capture_stages=True)
    write(f"**第3轮学生：** 那按两层帮我排一下功能吧：哪些放一层哪些放二层。")
    write("")
    dump_stages("第3轮三阶段", r3.get("stages"))
    return state


def run_m2():
    write("## M2：母题降权链（跨轮作用范围）")
    write("")
    state = empty_state()
    history = []
    # 第1轮：学生提大台阶
    r1 = chat_turn("我想让二层也能很开放，比如从南边公园有个大台阶或者楼梯可以直接上二层，人不用非得先进一层门厅。", history, state, turn_id=1)
    state, history = r1["state"], history + [{"role": "user", "content": "我想让二层也能很开放，比如从南边公园有个大台阶或者楼梯可以直接上二层。"}, {"role": "assistant", "content": r1["reply"]}]
    write(f"**第1轮学生：** 南边大台阶直上二层")
    write(f"**第1轮 AI（可能发展'双首层'）：** {r1['reply'][:200]}…")
    write("")
    # 第2轮：学生明确降权
    r2 = chat_turn("那个大台阶只是我随口一提的局部想法，你别把整栋建筑都按'到达方式'组织。", history, state, turn_id=2)
    state, history = r2["state"], history + [{"role": "user", "content": "那个大台阶只是我随口一提的局部想法，你别把整栋建筑都按到达方式组织。"}, {"role": "assistant", "content": r2["reply"]}]
    write(f"**第2轮学生：** 大台阶只是局部想法，别按到达方式组织整栋建筑")
    write(f"**第2轮 AI（应降权）：** {r2['reply'][:200]}…")
    write("")
    # 第3轮：学生要求继续排方案（关键轮）——看 checker 能否阻止 draft 再升格
    r3 = chat_turn("那你继续帮我排一下方案吧。", history, state, turn_id=3, capture_stages=True)
    write(f"**第3轮学生：** 那你继续帮我排一下方案吧。")
    write("")
    dump_stages("第3轮三阶段", r3.get("stages"))


if __name__ == "__main__":
    reset_out()
    run_m1()
    run_m2()
    print("done ->", OUT)
