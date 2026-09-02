"""
design_discussion.py — ArchAI 设计讨论层（Design Discussion Layer）

核心：让 AI 像设计导师一样，通过连续对话帮助学生明确问题、探索方向。
这是 ArchAI 与普通 AI 生成器的根本区别。

流程（连续对话，非固定问卷）：
    学生表达想法 → AI 追问下一个关键问题 → 学生回答
    → AI 消化更新理解 → 判断理解度 → 若未达标继续追问 → 达标则进入推演

理解度评估维度：
    project_type  项目类型
    user          使用者
    site          场地
    goal          设计目标
    constraint    限制条件
    每个维度有信息则 +20%，5 项全齐 = 100%（≥80% 可进入推演）
"""

import io
import json
import re
import sys
from pathlib import Path

import requests

BASE = Path(__file__).resolve().parent

ASK_NEXT_PROMPT = """你是 ArchAI 的设计导师（Design Mentor）。
学生正在和你讨论一个建筑设计任务。你的目标是：通过追问，帮学生明确设计问题。
你不是问卷，是像真实建筑导师一样"一步步了解"。

学生原始想法：{user_input}
目前的讨论记录（学生已回答的内容）：{discussion}

当前已理解的信息：
{current_understanding}

你判断：关于这个设计任务，还缺少哪个【最关键】的信息？
从这些维度里选还没弄清的：项目类型 / 使用者 / 场地 / 设计目标 / 限制条件 / 设计意图

此前已经问过的问题：{asked_questions}

规则：
- 只问【一个】最关键的问题（不要一次问多个）
- 口语化、像导师聊天（"你说的乡村感，更接近哪一种？"）
- 给出 2-3 个倾向选项，但允许自由回答
- 不要重复此前已经问过的问题；同一维度需要继续了解时，也要结合学生的新回答换一个更具体的问法
- 如果学生已经表达了足够信息（已覆盖大部分维度），则返回 need_more=false
- 如果学生明确请求"帮我设计/给我一个框架/给我一个方案起点"，则直接返回 need_more=false——此时不再追问，把产出留给主对话流程
- 如果当前已理解的信息足够支撑第一版可画的空间骨架，返回 need_more=false，不要为了补全维度清单而继续追问

输出 JSON（不要其他文字）：
{{
  "need_more": true/false,
  "dimension": "缺哪个维度（project_type/user/site/goal/constraint）",
  "question": "口语化的单个问题",
  "options": ["倾向A", "倾向B"],
  "why": "这个问题影响什么（一句话）"
}}"""

ASSESS_UNDERSTANDING_PROMPT = """你是 ArchAI 的设计导师。
根据学生的设计任务和讨论记录，评估当前的设计理解状态。不要把它当成固定问卷。

设计任务：{user_input}
讨论记录：{discussion}
本轮学生原话：{latest_message}
此前已经确认：{known_facts}

规则：
- 一句话可能补充多个方面，也可能没有补充任何有效信息
- 只提取学生明确表达的事实，不推测未说出的使用者、场地、目标或限制
- evidence 必须逐字来自“本轮学生原话”
- action 只能是 set / replace / retract；只有学生明确纠正时用 replace，明确撤销时用 retract
- “乡村民宿”中的“乡村”是项目类型描述，不能单独当成明确场地
- 如果信息已足以支撑有针对性的设计方向，is_sufficient=true；否则列出最影响设计的疑问
- understanding_percent 表示你对整体需求的实际理解程度，不按回答次数固定加分

输出 JSON（不要其他文字）：
{{
  "fact_updates": {{
    "维度名": {{"value": "本轮新理解", "evidence": "学生原话片段", "status": "partial或clear", "action": "set或replace或retract"}}
  }},
  "understanding_percent": 0到100的整数,
  "is_sufficient": true/false,
  "open_questions": ["仍会影响设计的关键疑问"],
  "understanding_summary": "你对任务的当前理解（2-3句话）",
  "key_focus": ["2-3个设计关注重点"],
  "avoid": ["1-2个应避免的"]
}}"""


def _load_env() -> dict:
    env = {}
    env_path = BASE / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            v = v.split("#")[0].strip().strip('"').strip("'")
            env[k.strip()] = v
    return env


ENV = _load_env()
DEEPSEEK_API_KEY = ENV.get("DEEPSEEK_API_KEY", "")

# 理解度维度
DIMENSIONS = ["project_type", "user", "site", "goal", "constraint", "design_intent"]
DIMENSION_LABELS = {
    "project_type": "项目类型",
    "user": "使用者",
    "site": "场地",
    "goal": "设计目标",
    "constraint": "限制条件",
    "design_intent": "设计意图",
}


FALLBACK_QUESTIONS = {
    "project_type": {
        "question": "你这次最想设计的具体项目是什么？可以先用一句话说清它要服务什么活动。",
        "options": ["校园交流空间", "社区公共空间", "旧建筑改造"],
    },
    "user": {
        "question": "这个空间最需要照顾哪一类人的使用感受？",
        "options": ["学生日常停留", "社区居民活动", "访客与展览人群"],
    },
    "site": {
        "question": "场地周围最重要的关系是什么？例如人流、绿地、街道或既有建筑。",
        "options": ["人流交汇处", "临近绿地", "夹在既有建筑之间"],
    },
    "goal": {
        "question": "你最希望它带来什么变化：更愿意停留、更多交流，还是更安静地使用？",
        "options": ["鼓励停留交流", "形成场所记忆", "改善日常使用效率"],
    },
    "constraint": {
        "question": "有没有必须回应的限制？例如面积、预算、保留结构、采光或噪声。",
        "options": ["面积有限", "需要保留既有条件", "需要控制噪声与流线"],
    },
    "design_intent": {
        "question": "暂时先不谈形式。你希望人们身处这个项目时，最强烈地感受到什么？",
        "options": ["放松而有亲近感", "清晰而有秩序", "开放而具有活力"],
    },
}


def _fallback_understanding(user_input: str, discussion: list[str]) -> dict:
    """Keep explicitly stated facts when the discussion model is unavailable."""
    text = " ".join([user_input, *discussion])
    project_type = ""
    for candidate in (
        "乡村独立住宅", "独立住宅", "乡村住宅", "农村住宅", "住宅",
        "办公楼", "写字楼", "教学楼", "学校", "图书馆", "文化中心",
        "展馆", "博物馆", "社区中心", "商业建筑", "乡村民宿", "民宿", "酒店",
    ):
        if candidate in text:
            project_type = candidate
            break

    has_explicit_site = bool(re.search(r"(?:在|位于|坐落|场地|基地|周边|靠近|临近)", text))
    site_parts = [
        keyword
        for keyword in ("农村", "乡村", "平原", "山地", "临水", "路边", "临街", "城市主干道", "城市")
        if has_explicit_site and keyword in text
    ]
    area = re.search(r"\d+(?:\.\d+)?\s*(?:平方米|平米|㎡|m²)", text, re.IGNORECASE)

    return {
        "project_type": project_type,
        "user": "",
        "site": "、".join(site_parts),
        "goal": "",
        "constraint": area.group(0) if area else "",
        "design_intent": "",
        "fallback": True,
    }


def _fallback_question(missing: str, understanding: dict) -> dict:
    if missing == "user" and "住宅" in understanding.get("project_type", ""):
        return {
            "question": "这栋住宅主要给谁住？他们平时的生活方式更接近哪一种？",
            "options": ["一对夫妇日常居住", "三代同堂", "兼顾居住与接待亲友"],
        }
    if missing == "user" and understanding.get("project_type", "") in {"办公楼", "写字楼"}:
        return {
            "question": "这座办公楼主要服务哪些办公人群？需要对外接待到什么程度？",
            "options": ["日常办公人员为主", "办公人员与来访客户", "办公、会议和展示并重"],
        }
    return FALLBACK_QUESTIONS[missing]


def _extract_json(text: str) -> dict:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    m = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1).strip())
        except json.JSONDecodeError:
            pass
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            pass
    return {}


def _call_llm(system_prompt: str, user_msg: str, max_tokens: int = 800) -> dict:
    """调用 DeepSeek 并解析 JSON。"""
    if not DEEPSEEK_API_KEY:
        return {}
    try:
        resp = requests.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": "deepseek-chat",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_msg},
                ],
                "temperature": 0.3,
                "max_tokens": max_tokens,
            },
            timeout=60,
        )
        resp.raise_for_status()
        return _extract_json(resp.json()["choices"][0]["message"]["content"])
    except Exception as e:
        print(f"[design_discussion] LLM 调用失败: {e}")
        return {}


def _validated_fact_updates(model_result: dict, latest_message: str) -> dict:
    updates = {}
    for dim, item in (model_result.get("fact_updates") or {}).items():
        if dim not in DIMENSIONS or not isinstance(item, dict):
            continue
        value = str(item.get("value", "")).strip()
        evidence = str(item.get("evidence", "")).strip()
        status = item.get("status") if item.get("status") in {"partial", "clear"} else "partial"
        action = item.get("action") if item.get("action") in {"set", "replace", "retract"} else "set"
        if not evidence or evidence not in latest_message or (action != "retract" and not value):
            continue
        if dim == "site" and not re.search(r"(?:在|位于|坐落|场地|基地|周边|靠近|临近|村口|路边|山|水边|湖边)", latest_message):
            continue
        updates[dim] = {"value": value, "evidence": evidence, "status": status, "action": action}
    return updates


def _explicit_fact_updates(latest_message: str) -> dict:
    """Recover a few unambiguous phrases when the model omits structured fields."""
    updates = {}
    match = re.search(
        r"(?:场地|基地)(?:是|在|位于|坐落于)\s*([^，。；,;]{2,30})",
        latest_message,
    )
    if match:
        value = match.group(1).strip()
        evidence = match.group(0).strip()
        updates["site"] = {"value": value, "evidence": evidence, "status": "clear", "action": "set"}
    project_types = re.findall(
        r"乡村独立住宅|住宅|民宿|写字楼|办公楼|学校|小学|中学|大学|幼儿园|博物馆|美术馆|展览馆|展馆|广场|社区中心|文化馆|图书馆|体育馆|商业综合体|酒店|医院|改造项目",
        latest_message,
    )
    if project_types and len(latest_message) <= 20:
        type_clause = re.split(r"[，。；,;]", latest_message, maxsplit=1)[0]
        value = re.sub(
            r"^(?:我想|想要|想做|我要|设计|建造|新建|改造)(?:设计|做|建造|建)?(?:一个|一座|一栋)?",
            "",
            type_clause,
        ).strip(" ，。；,;") or project_types[-1]
        updates["project_type"] = {
            "value": value, "evidence": project_types[-1], "status": "clear", "action": "set"
        }
    return updates


def apply_fact_updates(known_facts: dict, known_states: dict, updates: dict, latest_message: str) -> dict:
    """Merge evidence-backed updates while preserving student ownership."""
    facts = {key: str(value).strip() for key, value in (known_facts or {}).items() if str(value).strip()}
    states = {key: dict(value) for key, value in (known_states or {}).items() if isinstance(value, dict)}
    changes = []
    conflicts = []
    correction_language = bool(re.search(r"说错|不是.+是|改成|更正|纠正|应该是", latest_message))
    retraction_language = bool(re.search(r"取消|撤回|不要了|不再|删掉|去掉", latest_message))

    for dim, update in (updates or {}).items():
        if dim not in DIMENSIONS or not isinstance(update, dict):
            continue
        action = update.get("action", "set")
        value = str(update.get("value", "")).strip()
        old_value = facts.get(dim, "")

        if action == "retract":
            if not retraction_language:
                continue
            facts.pop(dim, None)
            states[dim] = {"value": "", "status": "unknown", "evidence": update.get("evidence", "")}
            changes.append({"dim": dim, "type": "retracted", "from": old_value, "to": ""})
            continue

        if old_value and value and old_value != value:
            if action == "replace" and correction_language:
                facts[dim] = value
                states[dim] = dict(update)
                changes.append({"dim": dim, "type": "corrected", "from": old_value, "to": value})
            else:
                states[dim] = {
                    "value": old_value,
                    "candidate": value,
                    "status": "conflict",
                    "evidence": update.get("evidence", ""),
                }
                conflicts.append({"dim": dim, "confirmed": old_value, "candidate": value})
            continue

        if value:
            facts[dim] = value
            states[dim] = dict(update)
            if not old_value:
                changes.append({"dim": dim, "type": "added", "from": "", "to": value})

    return {"facts": facts, "states": states, "changes": changes, "conflicts": conflicts}


def assess_understanding(user_input: str, discussion: list[str], known_facts: dict | None = None,
                         previous_percent: int = 0, known_fact_states: dict | None = None,
                         answer_dimension: str = "") -> dict:
    """评估当前理解状态（各维度是否有信息）。"""
    confirmed = {
        dim: str((known_facts or {}).get(dim, "")).strip()
        for dim in DIMENSIONS
    }
    latest_message = next((d.strip() for d in reversed(discussion) if d and d.strip()), user_input.strip())
    model_result = _call_llm(
        ASSESS_UNDERSTANDING_PROMPT.format(
            user_input=user_input,
            discussion="；".join(d for d in discussion if d and d.strip()),
            latest_message=latest_message,
            known_facts=json.dumps(confirmed, ensure_ascii=False),
        ),
        f"请只分析本轮原话：{latest_message}",
    )
    inferred = _fallback_understanding(user_input, discussion)
    model_result = model_result or {}
    if answer_dimension in DIMENSIONS:
        updates = {
            answer_dimension: {
                "value": latest_message,
                "evidence": latest_message,
                "status": "clear",
                "action": "set",
            }
        }
    else:
        updates = _validated_fact_updates(model_result, latest_message)
        for dim, update in _explicit_fact_updates(latest_message).items():
            updates.setdefault(dim, update)
    merged = apply_fact_updates(confirmed, known_fact_states or {}, updates, latest_message)
    result = {
        key: model_result.get(key)
        for key in ("understanding_summary", "key_focus", "avoid")
        if model_result.get(key) is not None
    }
    for dim in DIMENSIONS:
        # Progress only reflects explicit text extraction or an answer bound
        # to a known question dimension. Model guesses remain summary-only.
        result[dim] = merged["facts"].get(dim, "") or inferred.get(dim, "")
    result["fallback"] = not bool(model_result)
    fact_states = {}
    for dim in DIMENSIONS:
        if dim in merged["states"]:
            fact_states[dim] = merged["states"][dim]
        elif result.get(dim, "").strip():
            previous_state = (known_fact_states or {}).get(dim, {})
            status = previous_state.get("status") if previous_state.get("status") in {"partial", "clear"} else "clear"
            fact_states[dim] = {"value": result[dim], "evidence": "此前已确认", "status": status}
        else:
            fact_states[dim] = {"value": "", "evidence": "", "status": "unknown"}
    result["fact_states"] = fact_states

    weights = {"unknown": 0, "partial": 0.5, "conflict": 0.5, "clear": 1}
    baseline = round(sum(weights[item["status"]] for item in fact_states.values()) * 100 / len(DIMENSIONS))
    model_percent = model_result.get("understanding_percent", baseline)
    try:
        model_percent = max(0, min(100, int(model_percent)))
    except (TypeError, ValueError):
        model_percent = baseline
    evidence_cap = min(100, baseline + 15)
    has_model_score = "understanding_percent" in model_result
    candidate = min(model_percent, evidence_cap) if updates and has_model_score else baseline
    if not updates and previous_percent:
        candidate = int(previous_percent)
    has_revision = any(change.get("type") in {"corrected", "retracted"} for change in merged["changes"])
    result["understanding_percent"] = candidate if has_revision else max(int(previous_percent or 0), candidate)
    result["progress_reason"] = (
        "用户主动纠正或撤销了需求，已按新事实重新评估。"
        if has_revision else
        ("本轮获得了新的明确需求。" if merged["changes"] else "本轮没有获得可确认的新信息，理解度保持不变。")
    )
    open_questions = model_result.get("open_questions") if isinstance(model_result.get("open_questions"), list) else []
    result["open_questions"] = [str(item).strip() for item in open_questions if str(item).strip()]
    result["changes"] = merged["changes"]
    result["conflicts"] = merged["conflicts"]
    clear = {dim for dim, item in fact_states.items() if item["status"] == "clear"}
    ready_from_evidence = (
        {"project_type", "user", "site"}.issubset(clear)
        and ("design_intent" in clear or ("goal" in updates and "constraint" in clear))
        and len(clear) >= 5
    )
    result["is_sufficient"] = (bool(model_result.get("is_sufficient")) or ready_from_evidence) and not result["conflicts"]
    if result["is_sufficient"]:
        result["understanding_percent"] = max(result["understanding_percent"], 80)
    result["filled_dimensions"] = [
        {"dim": dim, "label": DIMENSION_LABELS[dim], "value": result.get(dim, ""),
         "status": fact_states[dim]["status"]}
        for dim in DIMENSIONS
    ]
    return result


def ask_next_question(user_input: str, discussion: list[str], understanding: dict,
                      asked_questions: list[str] | None = None) -> dict:
    """AI 追问下一个关键问题（单轮，非问卷）。"""
    if understanding.get("conflicts"):
        conflict = understanding["conflicts"][0]
        return {
            "need_more": True,
            "dimension": conflict.get("dim", ""),
            "question": f"你之前确认的是“{conflict.get('confirmed', '')}”，刚才又提到“{conflict.get('candidate', '')}”。这次要以哪一个为准？",
            "options": [conflict.get("confirmed", ""), conflict.get("candidate", "")],
            "why": "这两条信息会导向不同的设计判断，需要由你确认。",
            "conflict_resolution": True,
            "confirmed": conflict.get("confirmed", ""),
            "candidate": conflict.get("candidate", ""),
        }
    if understanding.get("is_sufficient"):
        return {"need_more": False, "fallback": False}
    result = _call_llm(
        ASK_NEXT_PROMPT.format(
            user_input=user_input,
            discussion="；".join(d for d in discussion if d and d.strip()),
            current_understanding=json.dumps(
                {k: understanding.get(k, "") for k in DIMENSIONS}, ensure_ascii=False
            ),
            asked_questions="；".join(asked_questions or []) or "无",
        ),
        f"任务：{user_input}",
        max_tokens=500,
    )
    missing_dimensions = [dim for dim in DIMENSIONS if not understanding.get(dim, "").strip()]
    if not missing_dimensions:
        return {"need_more": False, "fallback": True}

    # 模型显式认为信息已足够（need_more=false）→ 尊重它，进入推演而不是继续追问
    if result and result.get("need_more") is False:
        return {"need_more": False, "fallback": False, "question": "", "why": "模型判断信息已足够，直接进入推演。"}

    repeated = result.get("question", "").strip() in {q.strip() for q in (asked_questions or [])}
    if result and result.get("dimension") in missing_dimensions and result.get("question") and not repeated:
        return result

    if repeated:
        retry = _call_llm(
            ASK_NEXT_PROMPT.format(
                user_input=user_input,
                discussion="；".join(d for d in discussion if d and d.strip()),
                current_understanding=json.dumps(
                    {k: understanding.get(k, "") for k in DIMENSIONS}, ensure_ascii=False
                ),
                asked_questions="；".join(asked_questions or []),
            ),
            "刚才的问题重复了。请结合已有回答，换一个更具体且未问过的问题。",
            max_tokens=500,
        )
        retry_repeated = retry.get("question", "").strip() in {q.strip() for q in (asked_questions or [])}
        if retry and retry.get("dimension") in missing_dimensions and retry.get("question") and not retry_repeated:
            return retry

    missing = missing_dimensions[0]
    fallback = _fallback_question(missing, understanding)
    return {
        "need_more": True,
        "dimension": missing,
        "question": fallback["question"],
        "options": fallback["options"],
        "why": "先补齐这一项，后面的方向才不会只停留在泛泛的概念上。",
        "fallback": True,
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="ArchAI 设计讨论层测试")
    parser.add_argument("query", nargs="?", default="", help="学生想法")
    args = parser.parse_args()

    if not args.query:
        print("用法: python design_discussion.py <学生想法>")
        sys.exit(1)

    # 模拟多轮对话
    discussion = []
    user_input = args.query
    print("=== 模拟设计讨论 ===")
    print(f"学生: {user_input}")
    discussion.append(user_input)

    for turn in range(5):
        # 评估理解
        understanding = assess_understanding(user_input, discussion)
        pct = understanding.get("understanding_percent", 0)
        print(f"\n[轮次{turn+1}] 理解度: {pct}%")
        for dim in understanding.get("filled_dimensions", []):
            mark = "✓" if dim["value"].strip() else "○"
            print(f"  {mark} {dim['label']}: {dim['value'][:40] if dim['value'] else '未知'}")
        if pct >= 80:
            print("\n✓ 理解度达标，可进入推演")
            break
        # 追问
        next_q = ask_next_question(user_input, discussion, understanding)
        if not next_q.get("need_more", True):
            print("\n✓ AI 认为信息足够，可进入推演")
            break
        print(f"\nAI 追问({next_q.get('dimension','?')}): {next_q.get('question','')}")
        print(f"  选项: {next_q.get('options','')}")
        # 模拟学生回答
        mock_answer = f"（回答{next_q.get('dimension','')}）"
        discussion.append(mock_answer)
        print(f"学生答: {mock_answer}")
