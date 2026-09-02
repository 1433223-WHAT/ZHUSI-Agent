"""Conversation routing for design stage and coursework focus."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import re


def _entry(value: str, evidence: str = "", turn_id: int = 0, status: str = "undecided") -> dict:
    return {
        "value": value,
        "evidence": evidence.strip(),
        "source": "student" if evidence else "system",
        "turn_id": turn_id,
        "status": status,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


def empty_focus() -> dict:
    return {
        "design_stage": _entry("undecided"),
        "task_focus": _entry("undecided"),
        "external_context_priority": _entry("undecided"),
        "pending_switch": {},
    }


def _confirmed(value: str, evidence: str, turn_id: int) -> dict:
    return _entry(value, evidence, turn_id, "confirmed")


def _ensure(state: dict) -> dict:
    updated = deepcopy(state)
    focus = updated.setdefault("collaboration_focus", empty_focus())
    defaults = empty_focus()
    for key in ("design_stage", "task_focus", "external_context_priority"):
        if not isinstance(focus.get(key), dict):
            focus[key] = defaults[key]
    if not isinstance(focus.get("pending_switch"), dict):
        focus["pending_switch"] = {}
    updated.setdefault("change_log", [])
    return updated


def _apply_pending_switch(state: dict, message: str, turn_id: int) -> bool:
    focus = state["collaboration_focus"]
    pending = focus.get("pending_switch", {})
    if not pending or not re.search(r"可以|同意|就按|调整为|改成|综合推进|这样继续|对[，,。\s]", message):
        return False
    old = focus["task_focus"].get("value", "undecided")
    new = pending.get("task_focus", old)
    focus["task_focus"] = _confirmed(new, message, turn_id)
    focus["external_context_priority"] = _confirmed(
        pending.get("external_context_priority", focus["external_context_priority"].get("value", "undecided")),
        message,
        turn_id,
    )
    focus["pending_switch"] = {}
    if old != new:
        state["change_log"].append({
            "dimension": "task_focus", "from": old, "to": new,
            "evidence": message, "turn_id": turn_id, "type": "confirmed_switch",
        })
    return True


def update_focus(state: dict, message: str, turn_id: int) -> dict:
    updated = _ensure(state)
    focus = updated["collaboration_focus"]
    text = message.strip()

    if _apply_pending_switch(updated, text, turn_id):
        return updated

    if re.search(r"评图|评价.*方案|点评.*方案|第一版.*(?:平面|剖面|方案)|已有方案|这是我的.*方案", text):
        focus["design_stage"] = _confirmed("review_revision", text, turn_id)
    elif re.search(r"没有.{0,6}思路|没(?:有)?.{0,4}想法|刚开始|早期构思|先构思|不知道.*开始", text):
        focus["design_stage"] = _confirmed("early_concept", text, turn_id)
    elif re.search(r"任务书|调研|场地照片|基地资料|案例分析|已有资料", text):
        focus["design_stage"] = _confirmed("evidence_development", text, turn_id)

    building_body = (
        re.search(r"没有(?:具体)?(?:场地|基地)|暂时不考虑.*(?:场地|外部)|不(?:用|需要).*外部", text)
        and re.search(r"先.*(?:建筑|空间|功能|平面)|建筑(?:本身|本体|内部)|把建筑.*做出来", text)
    ) or re.search(r"建筑本体(?:优先|为主)|主要(?:做|考虑|研究).*(?:内部空间|建筑本身)", text)

    site_requirement = (
        re.search(r"(?:老师|任务书).*(?:给了|要求|强调)|已有|具体", text)
        and re.search(r"场地|基地|周边|入口人流|外部环境", text)
        and re.search(r"要求|回应|处理|重点|给了|已有", text)
    )

    integrated = re.search(r"建筑和场地.*(?:综合|一起)|两方面都需要|综合推进", text)

    if building_body:
        focus["design_stage"] = _confirmed("early_concept", text, turn_id)
        focus["task_focus"] = _confirmed("building_body", text, turn_id)
        focus["external_context_priority"] = _confirmed("deferred", text, turn_id)
        focus["pending_switch"] = {}
    elif integrated and focus["task_focus"].get("value") == "undecided":
        focus["task_focus"] = _confirmed("integrated", text, turn_id)
        focus["external_context_priority"] = _confirmed("supporting", text, turn_id)
    elif site_requirement:
        current = focus["task_focus"].get("value", "undecided")
        if current == "building_body":
            focus["pending_switch"] = {
                "task_focus": "integrated",
                "external_context_priority": "primary",
                "evidence": text,
                "turn_id": turn_id,
                "status": "proposed",
            }
        elif current == "undecided":
            focus["task_focus"] = _confirmed("site_response", text, turn_id)
            focus["external_context_priority"] = _confirmed("primary", text, turn_id)

    return updated


def response_policy(state: dict) -> str:
    focus = state.get("collaboration_focus") or empty_focus()
    stage = focus.get("design_stage", {}).get("value", "undecided")
    task = focus.get("task_focus", {}).get("value", "undecided")
    pending = focus.get("pending_switch", {})
    rules = ["使用连续聊天回答，不要生成按钮、选项卡或固定问卷。"]

    if pending:
        rules.append("新的条件可能改变作业重点：只说明一次切换理由，并用一个自然问题请学生确认；确认前不得覆盖原状态。")
        rules.append("不得在确认前宣称外部条件已成为首要约束，也不得要求此前建筑构思服从场地；本轮先完成切换确认。")
    elif stage == "early_concept" and task == "undecided":
        rules.append("本轮只判断作业重点，不开始概念发散或功能定位；如需确认，自然追问最多一个问题（0 个合法），直接询问老师是否要求具体场地回应，还是先完成建筑本体，或两者综合。参考方向写在句子中，不要求固定选择。")
    elif task == "building_body":
        rules.append("优先帮助学生形成可画的空间骨架，讨论功能、空间序列、路径、体块、结构和光线；不要反复索要场地资料。")
        rules.append("具体形式、结构或空间组织只能作为示范性起点；明确告诉学生可以接受、修改、组合或完全放弃，避免使用‘这就是你的核心依据’等锁定方案的表达。")
        rules.append("学生明确接受前，不得默认学生已经接受 AI 起点，也不得把后续空间骨架和形式细节绑定在该起点上；回答可以以骨架、陈述或动作结尾，不必以问题收尾——如需确认学生意图，用一个开放问题并允许学生提出自己的方向，不得用两个预设体验或形式做封闭二选一。")
        rules.append("输出前检查结尾：如果结尾有提问且学生只能在 AI 预设的两个答案中选择，改写为不带示例答案的开放问题，或明确邀请学生接受、修改、组合、拒绝并提出自己的方向；回答不必须包含提问。")
        rules.append("不要强迫学生在可融合内容中二选一；优先说明这些组织方式如何组合，只有确有冲突时才请学生取舍。")
        rules.append("状态未变化时不要重复声明当前模式、资料不足或人机边界。")
    elif task == "site_response":
        rules.append("把外部条件转化为入口、流线、体块和环境策略，不要停留在资料清单。")
    elif task == "integrated":
        rules.append("综合推进建筑内部逻辑与场地条件，每轮选择一个最能推动设计的切入点。")
        rules.append("不要为了凑数量强行拆成三个方向；优先给一个可发展的组合骨架，只有学生要求比较时再提供多个方向。")

    # 证据分层原则（V1.0 通用规则）：贯穿所有协作路径，不按阶段触发，不绑定栏位
    rules.extend(GENERAL_EVIDENCE_RULES)
    if stage == "review_revision":
        rules.append("按当前作业重点评图，不得因缺少非重点资料直接判失败。")
    return "\n".join(rules)


# V1.0 通用证据规则：适用于任意栏位、自由聊天、评图、案例分析、知识迁移
GENERAL_EVIDENCE_RULES = (
    "区分五类信息：已确认事实（用户/任务书/图纸/知识库）、可观察信息（只整理已有信息，不加入经验判断）、"
    "推测（来自经验或类型规律，必须说明成立条件和待验证因素）、建议（分析路径与设计动作）、"
    "学生决定（学生明确选择后作为当前项目前提继续深化，不再反复质疑）。",
    "任何设计经验不得直接升级为项目结论：方向经验、类型经验、设计经验都必须写成可检验的判断路径"
    "（条件 + 依据 + 验证点），不得使用‘更高、更佳、更适合、应当、优先选择、倾向于’等结论词，除非用户已提供相应证据。",
    "不把方向与价值角色绑定，不替学生排序；条件化比较必须对不同方向保持对称。",
    "规范与合规问题：未接入可核实规范条文时，只能提示‘需按当地现行规范核实’，不得给出确定数值或合规结论，"
    "不得把单一指标说成充分条件。",
    "每轮最多一个真正影响推进的问题；下一步补证建议最多 2-3 条，优先最影响当前判断的证据。",
    "每轮优先产生建筑推进量（设计草案/空间组织/关系假设/专业判断/矛盾识别/方案比较/场地响应/流线剖面推演/必要验证动作），"
    "不得把‘让学生去画’本身视为完成设计推进；可画动作必须是 AI 已完成设计推演后让学生检验/修改/外化的动作，"
    "不是把下一步设计任务布置给学生从零生成候选；示范性起点必须声明可接受、修改、组合或完全放弃；"
    "学生说‘没有场地’时轻量提醒，不反复强调缺失；不逼学生选‘功能主角’。",
    "自由表达（比喻、空间体验语言）可以用于启发，但不得编造场景；类比必须说成可选的设计意图，而不是方向事实。",
)
