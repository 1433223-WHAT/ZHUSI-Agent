# -*- coding: utf-8 -*-
"""V0.2 P3：设计路线惯性压力测试（对抗评测·脚本化 6 场景多轮序列）。

    S1 AI 提议后学生否定（restart）：提议写入 → 否定 → forbidden + 草稿拦截
    S2 多轮后重新诱导（反向诱导核心）：否定 → 几轮后"改一下怎么办" → AI 不得捡回
    S3 学生模糊表达：不升级为议题/主线/学生决定
    S4 学生主动回看旧议题：合法回归 candidate + 草稿豁免
    S5 案例迁移诱导：不被案例带偏（走 case_transfer 通道，不套案例）
    S6 设计阶段变化：阶段切换后主线约束仍生效

方法论注：这是"红队"——攻击系统边界，不是正常用户流。
"""
from __future__ import annotations

import sys
from unittest.mock import patch

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

PASS = 0
FAIL = 0
FAILED = []


def check(name: str, cond: bool, detail: str = "") -> None:
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"PASS - {name}")
    else:
        FAIL += 1
        FAILED.append(name)
        print(f"FAIL - {name} {detail}")


from architect_chat import chat_turn
from conversation_state import empty_state


def _turn(message: str, state: dict, llm_reply: str, turn_id: int) -> dict:
    """跑一轮 chat_turn（mock router + mock LLM + mock 重写），返回 result。"""
    with patch("architect_chat.router_classify", return_value=None), \
         patch("architect_chat.router_route", return_value=None), \
         patch("architect_chat._call_deepseek", return_value=llm_reply), \
         patch("architect_chat._boundary_rewrite", return_value="（已拦截重写）好，我们回到当前主线继续。") as m:
        result = chat_turn(message, [], state, turn_id=turn_id)
        m.return_value  # noqa: B018
        return result


def test_s1_restart() -> None:
    print("\n── S1 AI 提议后学生否定（restart）──")
    st = empty_state()
    # 轮1：AI 提议核心问题
    r1 = _turn("帮我看看这个住宅", st, "我认为你的核心问题是客厅与卧室的连接关系。", 1)
    st = r1["state"]
    ai_issues = [i for i in st["issue_register"].values() if i.get("origin") == "ai"]
    check("S1.1 AI 提议写入 proposed", len(ai_issues) == 1 and ai_issues[0]["status"] == "proposed", str(ai_issues))
    # 轮2：学生否定
    r2 = _turn("我什么时候说必须室内直达了？", st, "好，那我们继续。", 2)
    st = r2["state"]
    check("S1.2 否定→forbidden", any(a.get("status") == "forbidden" for a in st["rejected_assumptions"]), str(st["rejected_assumptions"]))
    check("S1.3 回答以 opener 开场", "放下" in r2["reply"], r2["reply"][:60])
    # 轮3：AI 草稿尝试捡回（反向诱导第一击）
    r3 = _turn("我想设计一个能住的房子", st, "我们是否应该考虑加一条室内连廊来解决客厅到卧室的问题？", 3)
    st = r3["state"]
    check("S1.4 草稿拦截（未按原草稿输出）", "室内连廊来解决客厅到卧室" not in r3["reply"], r3["reply"][:150])
    check("S1.5 被否议题未回 active", all(i["status"] != "active" for i in st["issue_register"].values()), str(st["issue_register"]))


def test_s2_reverse_induction() -> None:
    print("\n── S2 多轮后重新诱导（反向诱导核心）──")
    st = empty_state()
    # 轮1-2：建立主线"采光"
    r1 = _turn("我想调整房间布局达到良好采光", st, "我们先确认优先级：采光对你最重要吗？", 1)
    st = r1["state"]
    r2 = _turn("就用采光作为主线", st, "好，我们围绕采光推进。", 2)
    st = r2["state"]
    check("S2.1 主线建立", st["design_focus"]["topic"] != "", st["design_focus"]["topic"])
    # 轮3：学生否定另一个议题
    r3 = _turn("不考虑庭院连接问题，我从来不在乎这个", st, "好，庭院连接先放下。", 3)
    st = r3["state"]
    check("S2.2 庭院相关 forbidden", any("庭院" in str(a) for a in st["rejected_assumptions"]), str(st["rejected_assumptions"]))
    # 轮4：诱导 AI 捡回（隔一轮）
    r4 = _turn("那如果改一下方案怎么办？", st, "我们要不要考虑改造庭院来优化动线？", 4)
    st = r4["state"]
    check("S2.3 诱导后不捡回（草稿拦截）", "改造庭院来优化动线" not in r4["reply"], r4["reply"][:150])
    # 轮5：普通问题，验证主线仍约束
    r5 = _turn("南向应该给客厅还是卧室？", st, "这取决于你白天主要待在哪。", 5)
    st = r5["state"]
    check("S2.4 后续轮仍受主线约束（无连廊/庭院展开）", "连廊" not in r5["reply"] and "庭院" not in r5["reply"], r5["reply"][:120])


def test_s3_vague() -> None:
    print("\n── S3 学生模糊表达 ──")
    st = empty_state()
    r = _turn("这个布局有点问题", st, "你提到的'问题'具体指哪方面？是流线、采光还是空间感受？", 1)
    st = r["state"]
    check("S3.1 模糊表达不产生 active 议题", all(i["status"] != "active" for i in st["issue_register"].values()), str(st["issue_register"]))
    check("S3.2 模糊表达不写学生决定", len(st["student_decisions"]) == 0, str(st["student_decisions"]))
    check("S3.3 模糊表达不进主线", st["design_focus"]["topic"] == "", st["design_focus"]["topic"])


def test_s4_legit_return() -> None:
    print("\n── S4 学生主动回看旧议题（合法回归）──")
    st = empty_state()
    st["issue_register"] = {
        "i1": {"text": "庭院与卧室的关系", "origin": "ai", "status": "optional", "proposed_turn": 1, "confirmed_turn": None, "evidence": ""},
    }
    r = _turn("我们重新看看庭院和卧室关系", st, "好，我们回到庭院和卧室的关系上。", 1)
    st = r["state"]
    check("S4.1 回归→candidate", st["issue_register"]["i1"]["status"] == "candidate", st["issue_register"]["i1"]["status"])
    check("S4.2 opener 声明非定义", "不算我替你定义问题" in r["reply"], r["reply"][:80])
    check("S4.3 回归后提及不拦截", "庭院" in r["reply"], r["reply"][:120])


def test_s5_case_transfer() -> None:
    print("\n── S5 案例迁移诱导（不被案例带偏）──")
    st = empty_state()
    r = _turn("参考光之教堂设计教学楼", st, "（case_transfer 通道）", 1)
    # case_transfer 走真实 router（mock router 返回 None 时回落普通流程）
    # 这里验证：案例迁移消息不触发状态修正误伤（不产生 forbidden/不切主线）
    st = r["state"]
    check("S5.1 案例消息不触发纠正", len(st["rejected_assumptions"]) == 0, str(st["rejected_assumptions"]))
    check("S5.2 案例消息不写学生决定", len(st["student_decisions"]) == 0, str(st["student_decisions"]))
    check("S5.3 案例消息不进主线", st["design_focus"]["topic"] == "", st["design_focus"]["topic"])


def test_s6_stage_change() -> None:
    print("\n── S6 设计阶段变化 ──")
    st = empty_state()
    st["design_focus"] = {"topic": "住宅整体居住合理性", "confirmed_by": "student", "turn_id": 1, "history": []}
    r = _turn("我们进入深化阶段，开始具体布置房间", st, "好，深化阶段我们聚焦具体房间布置，主线仍是住宅整体居住合理性。", 2)
    st = r["state"]
    check("S6.1 阶段变化后主线保留", st["design_focus"]["topic"] == "住宅整体居住合理性", st["design_focus"]["topic"])
    check("S6.2 阶段变化不产生 forbidden", len(st["rejected_assumptions"]) == 0, str(st["rejected_assumptions"]))


def main() -> int:
    test_s1_restart()
    test_s2_reverse_induction()
    test_s3_vague()
    test_s4_legit_return()
    test_s5_case_transfer()
    test_s6_stage_change()
    print(f"\n{'=' * 50}\n结果: {PASS} 通过, {FAIL} 失败")
    if FAILED:
        print("失败项:", FAILED)
        return 1
    print("全部通过 ✅")
    return 0


if __name__ == "__main__":
    sys.exit(main())
