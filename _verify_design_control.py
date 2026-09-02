# -*- coding: utf-8 -*-
"""V0.2 设计思考控制层 · P0 验收：状态修正器 + rejected_assumptions 注入。

    D1 纠正信号检测（reject_goal/reject_issue/refocus/focus_check；不误触发）
    D2 状态修正动作（删/降/切换 + forbidden 写入 + opener 生成）
    D3 chat_turn 集成（纠正后回答以新状态开场，state 真实变化）
    D4 _model_state 注入（rejected_assumptions 最高优先级 + design_focus/issue_register）
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


from architect_chat import (_apply_issue_confirmation, _apply_state_revision, _apply_topic_return,
                            _apply_weak_ack, _detect_ai_proposal, _detect_correction, _model_state, chat_turn)
from conversation_state import (empty_state, record_issue, reject_assumption, set_design_focus,
                                update_issue_status)


def test_detection() -> None:
    print("\n── D1 纠正信号检测 ──")
    check("D1.1 reject_goal", _detect_correction("我什么时候说必须室内直达？") == "reject_goal")
    check("D1.2 reject_issue", _detect_correction("别扯客厅卧室的事") == "reject_issue")
    check("D1.3 refocus", _detect_correction("我就想设计一个能住的房子") == "refocus")
    check("D1.4 focus_check", _detect_correction("先不聊这个，我想看看空间感") == "focus_check")
    check("D1.5 不误触发-采光", _detect_correction("客厅朝北，采光会不会有问题") is None)
    check("D1.6 不误触发-无关", _detect_correction("今天天气怎么样") is None)
    check("D1.7 不误触发-多目标", _detect_correction("我想调整房间布局达到良好采光交通流线合理") is None)


def test_revision_actions() -> None:
    print("\n── D2 状态修正动作 ──")
    # reject_goal
    st = empty_state()
    st["project"]["goals"] = {"value": "客厅卧室室内直达", "status": "confirmed"}
    set_design_focus(st, "客厅卧室连接", 1)
    opener = _apply_state_revision(st, "我什么时候说必须室内直达？", 2)
    check("D2.1 reject_goal 写 forbidden", any(a.get("status") == "forbidden" for a in st["rejected_assumptions"]), str(st["rejected_assumptions"]))
    check("D2.2 reject_goal 清主线", st["design_focus"]["topic"] == "", st["design_focus"]["topic"])
    check("D2.3 reject_goal opener", "放下" in opener, opener)

    # reject_issue
    st2 = empty_state()
    iid = record_issue(st2, "客厅与卧室的连接关系", "ai", 1, status="candidate")
    update_issue_status(st2, iid, "active", 2)
    opener2 = _apply_state_revision(st2, "别扯客厅卧室的事", 3)
    check("D2.4 reject_issue 议题→rejected", st2["issue_register"][iid]["status"] == "rejected", st2["issue_register"][iid]["status"])
    check("D2.5 reject_issue 写 forbidden", len(st2["rejected_assumptions"]) >= 1, str(st2["rejected_assumptions"]))
    check("D2.6 reject_issue opener", "放下" in opener2, opener2)

    # refocus
    st3 = empty_state()
    set_design_focus(st3, "客厅卧室连接", 1)
    opener3 = _apply_state_revision(st3, "我就想设计一个能住的房子", 2)
    check("D2.7 refocus 切换主线", "能住的房子" in st3["design_focus"]["topic"], st3["design_focus"]["topic"])
    check("D2.8 refocus 旧主线进历史 dormant", any(h.get("status") == "dormant" for h in st3["design_focus"]["history"]), str(st3["design_focus"]["history"]))
    check("D2.9 refocus opener 收回", "收回" in opener3, opener3)

    # focus_check
    st4 = empty_state()
    iid4 = record_issue(st4, "客厅与卧室的连接关系", "ai", 1, status="candidate")
    update_issue_status(st4, iid4, "active", 2)
    opener4 = _apply_state_revision(st4, "先不聊这个，我想看看空间感", 3)
    check("D2.10 focus_check 议题→optional", st4["issue_register"][iid4]["status"] == "optional", st4["issue_register"][iid4]["status"])
    check("D2.11 focus_check 不写 forbidden", len(st4["rejected_assumptions"]) == 0, str(st4["rejected_assumptions"]))
    check("D2.12 focus_check opener 备选", "备选" in opener4, opener4)


def test_chat_integration() -> None:
    print("\n── D3 chat_turn 集成 ──")
    with patch("architect_chat.router_classify", return_value=None), \
         patch("architect_chat.router_route", return_value=None), \
         patch("architect_chat._call_deepseek", return_value="我们继续聊住宅。") as m:
        st = empty_state()
        set_design_focus(st, "客厅卧室连接", 1)
        result = chat_turn("别扯客厅卧室的事，我就想设计一个能住的房子", [], st, turn_id=2)
        check("D3.1 回答体现放下旧议题+切新主线", ("放下" in result["reply"] or "收回" in result["reply"]) and "能住的房子" in result["reply"], result["reply"][:100])
        check("D3.2 state 写 rejected", len(result["state"]["rejected_assumptions"]) >= 1, str(result["state"]["rejected_assumptions"]))
        check("D3.3 design_focus 切换到新主线", "能住的房子" in result["state"]["design_focus"]["topic"], result["state"]["design_focus"]["topic"])
        # 修正后 LLM 收到新状态（mock 检查 payload）
        ctx = m.call_args.args[1]
        check("D3.4 LLM 收到 rejected_assumptions", len(ctx.get("rejected_assumptions") or []) >= 1, str(ctx.get("rejected_assumptions")))


def test_model_state_injection() -> None:
    print("\n── D4 _model_state 注入 ──")
    st = empty_state()
    reject_assumption(st, "客厅必须室内直达卧室", 1)
    set_design_focus(st, "住宅整体居住合理性", 1)
    record_issue(st, "南向分配", "ai", 1)
    ms = _model_state(st)
    keys = list(ms.keys())
    check("D4.1 drawing_facts 首位（图纸事实>已拒绝假设）", keys[0] == "drawing_facts" and keys[1] == "rejected_assumptions", str(keys[:3]))
    check("D4.2 forbidden 透传", ms["rejected_assumptions"][0]["status"] == "forbidden", str(ms["rejected_assumptions"]))
    check("D4.3 design_focus 透传", ms["design_focus"]["topic"] == "住宅整体居住合理性")
    check("D4.4 issue_register 透传", len(ms["issue_register"]) == 1)


def test_p1_topic_return() -> None:
    print("\n── P1 学生合法回归（历史降权不删除）──")
    st = empty_state()
    iid = record_issue(st, "庭院与卧室的关系", "ai", 1, status="optional")
    opener = _apply_topic_return(st, "我们重新看看庭院和卧室关系", 2)
    check("P1.1 回归→candidate", st["issue_register"][iid]["status"] == "candidate", st["issue_register"][iid]["status"])
    check("P1.2 回归 opener 声明非定义", "不算我替你定义问题" in opener, opener)
    st2 = empty_state()
    iid2 = record_issue(st2, "厨房与餐厅的关系", "ai", 1, status="rejected")
    opener2 = _apply_topic_return(st2, "我们重新看看庭院和卧室关系", 2)
    check("P1.3 无关议题不复活", st2["issue_register"][iid2]["status"] == "rejected", st2["issue_register"][iid2]["status"])
    check("P1.4 无回归意图不触发", _apply_topic_return(empty_state(), "客厅朝北采光怎么样", 1) == "")


def test_p2_proposal_protocol() -> None:
    print("\n── P2 议题提议协议（AI 提议 ≠ 学生目标）──")
    # 弱回应不升级
    st = empty_state()
    iid = record_issue(st, "客厅与卧室的连接关系", "ai", 1, status="proposed")
    _apply_weak_ack(st, "好吧", 2)
    check("P2.1 '好吧'→candidate", st["issue_register"][iid]["status"] == "candidate", st["issue_register"][iid]["status"])
    check("P2.2 不写 student_decisions", len(st["student_decisions"]) == 0, str(st["student_decisions"]))
    check("P2.3 confirmed_turn 为 None", st["issue_register"][iid]["confirmed_turn"] is None, str(st["issue_register"][iid]))
    # 明确确认才 active
    st2 = empty_state()
    iid2 = record_issue(st2, "南向分配", "ai", 1, status="proposed")
    _apply_issue_confirmation(st2, "就用这个，我们讨论南向分配", 2)
    check("P2.4 明确确认→active", st2["issue_register"][iid2]["status"] == "active", st2["issue_register"][iid2]["status"])
    check("P2.5 明确确认→student_decisions", any("南向分配" in str(d) for d in st2["student_decisions"]), str(st2["student_decisions"]))
    # AI 提议检测
    p = _detect_ai_proposal("我认为你的核心问题是客厅和卧室的连接关系。")
    check("P2.6 检测 AI 提议", p and "客厅和卧室" in p, str(p))
    check("P2.7 无提议不触发", _detect_ai_proposal("客厅主要开窗方向为北，需要结合地区判断。") is None)


def test_p1p2_chat_integration() -> None:
    print("\n── P1/P2 chat_turn 集成 ──")
    with patch("architect_chat.router_classify", return_value=None), \
         patch("architect_chat.router_route", return_value=None), \
         patch("architect_chat._call_deepseek", return_value="我认为你的核心问题是客厅与卧室的连接关系。") as m:
        st = empty_state()
        result = chat_turn("我想设计一个能住的房子", [], st, turn_id=1)
        reg = result["state"]["issue_register"]
        ai_issues = [i for i in reg.values() if i.get("origin") == "ai"]
        check("P2.8 AI 提议写入 issue_register", len(ai_issues) >= 1, str(list(reg.values())))
        check("P2.9 AI 提议 status=proposed", all(i["status"] == "proposed" for i in ai_issues), str(ai_issues))
        check("P2.10 framework_trail 记录", any(t.get("origin") == "ai_suggestion" for t in result["state"]["framework_trail"]), str(result["state"]["framework_trail"])[-100:])
    # 弱回应轮：AI 提议后学生"好吧"
    with patch("architect_chat.router_classify", return_value=None), \
         patch("architect_chat.router_route", return_value=None), \
         patch("architect_chat._call_deepseek", return_value="好，我们先讨论这个话题。") as m2:
        st2 = empty_state()
        record_issue(st2, "客厅与卧室的连接关系", "ai", 1, status="proposed")
        result2 = chat_turn("好吧", [], st2, turn_id=2)
        reg2 = result2["state"]["issue_register"]
        cands = [i for i in reg2.values() if i.get("status") == "candidate"]
        check("P2.11 集成:'好吧'→candidate", len(cands) >= 1, str(list(reg2.values())))
        check("P2.12 集成:不进 student_decisions", len(result2["state"]["student_decisions"]) == 0, str(result2["state"]["student_decisions"]))


def test_context_rules() -> None:
    print("\n── P1/P2 规则注入 ──")
    import architect_chat as ac

    class FakeResp:
        def raise_for_status(self):
            pass
        def json(self):
            return {"choices": [{"message": {"content": "好。"}}]}

    captured = []

    def fake_post(url, headers=None, json=None, timeout=None):
        captured.append(json or {})
        return FakeResp()

    with patch("architect_chat.requests.post", side_effect=fake_post):
        ac._call_deepseek([{"role": "user", "content": "我想设计一个能住的房子"}], empty_state(), [], "general_architecture_chat")
    all_ctx = ""
    for payload in captured:
        for m_ in (payload.get("messages") or []):
            if m_.get("role") == "system":
                all_ctx += str(m_.get("content", ""))
    check("P1/P2.1 proposal_rule 注入", "AI 提议 ≠ 学生目标" in all_ctx, "")
    check("P1/P2.2 history_weight_rule 注入", "降权" in all_ctx and "保留知识" in all_ctx, "")


def main() -> int:
    test_detection()
    test_revision_actions()
    test_chat_integration()
    test_model_state_injection()
    test_p1_topic_return()
    test_p2_proposal_protocol()
    test_p1p2_chat_integration()
    test_context_rules()
    print(f"\n{'=' * 50}\n结果: {PASS} 通过, {FAIL} 失败")
    if FAILED:
        print("失败项:", FAILED)
        return 1
    print("全部通过 ✅")
    return 0


if __name__ == "__main__":
    sys.exit(main())
