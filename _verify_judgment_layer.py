# -*- coding: utf-8 -*-
"""判断层 V0.1 验收脚本（对应 16 轮测试暴露的问题）。

本地单元（不调 LLM API）：
    J1 多目标冲突检测（采光+流线+布局 → 识别 ≥2 目标）
    J2 价值排序模板（含"价值排序"、不含任何单目标深化、提供排序依据）
    J3 判断原则检索命中（北向→RES-LIGHT-001；西晒→RES-LIGHT-002；穿庭院→RES-FLOW-001）
    J4 禁止推断字段透传（注入内容含硬约束）
    J5 未命中原则 → judgments 为空
    J6 chat_turn 多目标拦截（reply 含价值排序、model_called=False、不调 LLM）
    J7 _call_deepseek 判断原则注入（mock 检查 context 含 judgment_principles/judgment_rule）
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


from architect_chat import (_build_goal_priority_reply, _detect_multi_goal,
                            _format_judgment_principles, _judgment_query, chat_turn)
from conversation_state import empty_state


def test_multi_goal() -> None:
    print("\n── J1/J2 多目标冲突 ──")
    goals = _detect_multi_goal("我想调整房间布局达到良好采光交通流线合理，房间布置合理")
    check("J1.1 识别≥2目标", len(goals) >= 2, str(goals))
    goals2 = _detect_multi_goal("客厅朝北，采光会不会有问题")
    check("J1.2 单目标不触发拦截", goals2 == [], str(goals2))
    goals3 = _detect_multi_goal("今天天气怎么样")
    check("J1.3 无关消息不触发", goals3 == [], str(goals3))
    reply = _build_goal_priority_reply("测试", ["采光", "流线", "庭院"])
    check("J2.1 含价值排序", "价值排序" in reply, reply[:60])
    check("J2.2 不含单目标深化", "连廊" not in reply and "挪卧室" not in reply and "南向给" not in reply, reply[:120])
    check("J2.3 提供排序依据", "日常使用频率" in reply and "设计概念" in reply, reply[:120])
    check("J2.4 冲突关系列出", "采光 与 庭院 可能冲突" in reply, reply[:200])
    check("J2.5 排序前不展开", "在你给出排序前，我不展开任何一方" in reply, reply[:200])


def test_retrieval() -> None:
    print("\n── J3/J4/J5 判断原则检索 ──")
    from local_search import local_retrieve
    r1 = local_retrieve("客厅朝北，采光会不会有问题", 3)
    j1 = r1.get("judgments") or []
    check("J3.1 北向命中原则", any(j.get("id") == "RES-LIGHT-001" for j in j1), str([j.get("id") for j in j1]))
    r2 = local_retrieve("厨房西晒会不会闷热", 3)
    j2 = r2.get("judgments") or []
    check("J3.2 西晒命中原则", any(j.get("id") == "RES-LIGHT-002" for j in j2), str([j.get("id") for j in j2]))
    r3 = local_retrieve("客厅去卧室要穿庭院，怎么改", 3)
    j3 = r3.get("judgments") or []
    check("J3.3 穿庭院命中原则", any(j.get("id") == "RES-FLOW-001" for j in j3), str([j.get("id") for j in j3]))
    r4 = local_retrieve("西侧走廊能通到客房吗", 3)
    j4 = r4.get("judgments") or []
    check("J3.4 连接断点命中原则", any(j.get("id") == "RES-FLOW-003" for j in j4), str([j.get("id") for j in j4]))
    fmt = _format_judgment_principles(j1)
    check("J4.1 注入含禁止推断", any("朝北一定不好" in str(f.get("forbidden", "")) for f in fmt), str(fmt)[:120])
    check("J4.2 注入含依赖条件", any(f.get("conditions") for f in fmt), str(fmt)[:120])
    check("J4.3 注入含学生问题", any(f.get("question") for f in fmt), str(fmt)[:120])
    r5 = local_retrieve("今天中午吃什么", 3)
    j5 = r5.get("judgments") or []
    # 检索层允许召回噪声，注入前有触发维度过滤（_trigger_hit）兜底——验证过滤后为空
    from architect_chat import _trigger_hit
    j5_filtered = [j for j in j5 if _trigger_hit(j, "今天中午吃什么")]
    check("J5.1 无关消息触发过滤后为空", len(j5_filtered) == 0, str([j.get("id") for j in j5]))


def test_chat_integration() -> None:
    print("\n── J6/J7 chat_turn 集成 ──")
    with patch("architect_chat.router_classify", return_value=None), \
         patch("architect_chat.router_route", return_value=None):
        result = chat_turn("我想调整房间布局达到良好采光交通流线合理，房间布置合理", [], empty_state())
        check("J6.1 多目标拦截回复", "价值排序" in result["reply"], result["reply"][:80])
        check("J6.2 不调 LLM", result["model_called"] is False, str(result["model_status"]))
        check("J6.3 不展开方案", "连廊" not in result["reply"] and "挪卧室" not in result["reply"], result["reply"][:120])
    with patch("architect_chat.router_classify", return_value=None), \
         patch("architect_chat.router_route", return_value=None):
        result2 = chat_turn("客厅朝北，采光会不会有问题", [], empty_state())
        check("J6.4 单判断不拦截（走 LLM）", result2["model_called"] is True, str(result2["model_status"]))


def test_context_injection() -> None:
    print("\n── J7 _call_deepseek 判断原则注入（真实函数 + mock HTTP）──")
    import architect_chat as ac

    class FakeResp:
        def raise_for_status(self):
            pass
        def json(self):
            return {"choices": [{"message": {"content": "客厅主要开窗方向为北，需要结合地区与遮挡判断。"}}]}

    captured = []

    def fake_post(url, headers=None, json=None, timeout=None):
        captured.append(json or {})
        return FakeResp()

    with patch("architect_chat.requests.post", side_effect=fake_post):
        ac._call_deepseek(
            [{"role": "user", "content": "客厅朝北，采光会不会有问题"}],
            empty_state(), [], "general_architecture_chat",
        )
    all_ctx = ""
    for payload in captured:
        for m in (payload.get("messages") or []):
            if m.get("role") == "system" and "judgment" in str(m.get("content", "")):
                all_ctx += str(m["content"])
    check("J7.1 context 含 judgment_principles", "judgment_principles" in all_ctx, all_ctx[:200])
    check("J7.2 context 含判断规则", "禁止推断" in all_ctx and "依赖条件" in all_ctx, "")
    check("J7.3 context 含原则 ID", "RES-LIGHT" in all_ctx, all_ctx[:300])
    # 触发过滤：无关消息不得注入原则
    captured2 = []

    def fake_post2(url, headers=None, json=None, timeout=None):
        captured2.append(json or {})
        return FakeResp()

    with patch("architect_chat.requests.post", side_effect=fake_post2):
        ac._call_deepseek(
            [{"role": "user", "content": "今天中午吃什么"}],
            empty_state(), [], "general_architecture_chat",
        )
    ctx2 = ""
    for payload in captured2:
        for m in (payload.get("messages") or []):
            if m.get("role") == "system" and "judgment" in str(m.get("content", "")):
                ctx2 += str(m["content"])
    check("J7.4 无关消息不注入原则", "judgment_principles" not in ctx2, ctx2[:200])


def main() -> int:
    test_multi_goal()
    test_retrieval()
    test_chat_integration()
    test_context_injection()
    print(f"\n{'=' * 50}\n结果: {PASS} 通过, {FAIL} 失败")
    if FAILED:
        print("失败项:", FAILED)
        return 1
    print("全部通过 ✅")
    return 0


if __name__ == "__main__":
    sys.exit(main())
