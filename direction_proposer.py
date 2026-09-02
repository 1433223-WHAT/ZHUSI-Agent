"""
direction_proposer.py — ArchAI 设计方向提案器（Design Direction Proposer）

核心：Human-in-the-loop 的关键环节。
AI 基于任务分析和知识检索结果，提出 3 个差异化设计方向，让学生选择。

流程：
    Task Analyzer → 知识检索 → 【本模块：AI 提 3 方向】→ 学生选择 → 按方向生成

输出（每个方向）：
    {
      "name": "开放共享型",
      "strategy": "底层架空 + 中庭交流",
      "cases": ["克朗楼", "卡朋特中心"],
      "description": "以开放共享为核心，将建筑底层释放为校园公共客厅…"
    }
"""

import io
import json
import re
import sys
from pathlib import Path

import requests

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))

from task_analyzer import analyze_task, build_search_query  # noqa: E402
from agent_tools import case_search, method_search, theory_search  # noqa: E402

PROPOSER_PROMPT = """你是 ArchAI 建筑设计智能体的设计方向提案器。
你的目标：帮助建筑学生快速理解任务并做出设计方向决策。你是"设计助手"，不是"评图老师"。

语言要求（最重要）：
- 简洁、行动导向，30%解释 + 70%可执行的建议
- 不要用"营造超越日常的精神性纪念体验"这种论文腔
- 要像导师在学生画草图前说的那句：短、准、有用

输出包含两部分：

注意：你可能收到 design_context（学生此前讨论形成的设计认知，含 user_intention/key_focus/avoid）。
必须尊重它——提出的方向要贴合学生的设计意图和关注重点，避免学生明确要避免的方向。

A. 设计驾驶舱（帮助学生快速理解任务，控制在一屏）
- core_conflict: 一句话核心矛盾（任务最关键的张力，口语化，如"场地想要安静，但学生天天路过，怎么两全？"）
- key_questions: 3 个设计挑战（用"挑战"口吻，如"如何避免普通建筑感，形成纪念体验？"）
  - 每条是学生"下一步要想什么"，不是论文命题

B. 方向推演（3 个差异化方向，每张卡片信息量极小）
每个方向只保留：
- name: 方向名（如"光之甬道·静谧沉思型"，短）
- core_strategy: 一句话核心策略（如"用连续光线+路径控制制造仪式感"）
- suitable_for: 适合什么（1-2个词，如"纪念馆/展示空间"）
- cases: 参考案例（1-2个）
- risk: 风险（一句话，如"可能削弱开放交流"）
- description: 120字内简短描述（可选，折叠展示）
- evidence: 每条方向都必须给出本次检索结果中的 case / theory / method 各一条，并用 why 简述它如何支持这条策略
- case.fit: 评估案例与当前项目的项目类型、尺度、功能、场地气候匹配度，并写明可迁移、不可照搬和风险

要求：
- 3 个方向差异化明显
- 每个方向必须基于检索到的案例策略
- evidence 中的 name 必须逐字选自输入里的 retrieved_cases、retrieved_theories、retrieved_methods，不能补写、猜测或编造来源
- 方向要可执行（学生选完能直接生成）

输出 JSON（不要其他文字）：
{
  "core_conflict": "一句话核心矛盾",
  "key_questions": ["挑战1", "挑战2", "挑战3"],
  "directions": [
    {
      "name": "方向名",
      "core_strategy": "一句话核心策略",
      "suitable_for": "适合场景",
      "cases": ["案例名1"],
      "risk": "风险",
      "description": "120字内描述",
      "evidence": {
        "case": {
          "name": "检索到的案例名",
          "why": "案例策略如何支持本方向",
          "fit": {
            "project_type": 0到100,
            "scale": 0到100,
            "function": 0到100,
            "site_climate": 0到100,
            "transferable": "可迁移的部分",
            "not_copy": "不能直接照搬的部分",
            "risk": "迁移风险"
          }
        },
        "theory": {"name": "检索到的理论名", "why": "理论如何帮助判断"},
        "method": {"name": "检索到的方法名", "why": "方法如何落实为空间手段"}
      }
    },
    ...3个
  ]
}"""


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


def _filter_relevant_knowledge(cases: list[dict], theories: list[dict], methods: list[dict]) -> tuple[list[dict], list[dict], list[dict]]:
    """Remove only clearly unrelated vector hits; fit validation remains separate."""
    return (
        [item for item in cases if float(item.get("score", 0) or 0) >= 0.32],
        [item for item in theories if float(item.get("score", 0) or 0) >= 0.26],
        [item for item in methods if float(item.get("score", 0) or 0) >= 0.27],
    )


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


def _validate_direction_evidence(directions: list[dict], cases: list[dict], theories: list[dict], methods: list[dict]) -> bool:
    """Reject citations not returned by this retrieval run."""
    allowed = {
        "case": {item.get("name") for item in cases if item.get("name")},
        "theory": {item.get("name") for item in theories if item.get("name")},
        "method": {item.get("name") for item in methods if item.get("name")},
    }
    if not all(allowed.values()):
        return False
    for direction in directions:
        evidence = direction.get("evidence", {})
        for kind in ("case", "theory", "method"):
            item = evidence.get(kind, {})
            if not isinstance(item, dict) or item.get("name") not in allowed[kind] or not item.get("why", "").strip():
                return False
    return True


def _verified_evidence(direction: dict, cases: list[dict], theories: list[dict], methods: list[dict]) -> dict:
    """Keep the model rationale, but replace source data with canonical retrieved entries."""
    lookup = {
        "case": {item["name"]: item for item in cases if item.get("name")},
        "theory": {item["name"]: item for item in theories if item.get("name")},
        "method": {item["name"]: item for item in methods if item.get("name")},
    }
    result = dict(direction)
    evidence = direction["evidence"]
    raw_fit = evidence["case"].get("fit", {}) if isinstance(evidence["case"], dict) else {}
    fit = {}
    for key in ("project_type", "scale", "function", "site_climate"):
        try:
            fit[key] = max(0, min(100, int(raw_fit.get(key, 0))))
        except (TypeError, ValueError):
            fit[key] = 0
    for key in ("transferable", "not_copy", "risk"):
        fit[key] = str(raw_fit.get(key, "")).strip()
    fit["average"] = round(sum(fit[key] for key in ("project_type", "scale", "function", "site_climate")) / 4)
    result["evidence"] = {
        "case": {
            "name": evidence["case"]["name"],
            "strategy": lookup["case"][evidence["case"]["name"]].get("strategy", ""),
            "source_text": lookup["case"][evidence["case"]["name"]].get("content", ""),
            "why": evidence["case"]["why"],
            "fit": fit,
        },
        "theory": {
            "name": evidence["theory"]["name"],
            "source_text": lookup["theory"][evidence["theory"]["name"]].get("content", ""),
            "why": evidence["theory"]["why"],
        },
        "method": {
            "name": evidence["method"]["name"],
            "source_text": lookup["method"][evidence["method"]["name"]].get("content", ""),
            "why": evidence["method"]["why"],
        },
    }
    complete_fit = all(fit[key] for key in ("transferable", "not_copy", "risk"))
    result["evidence_status"] = "verified" if complete_fit and fit["average"] >= 60 else "partial"
    return result


def _knowledge_note(cases: list[dict], theories: list[dict], methods: list[dict]) -> dict:
    missing = []
    if not cases:
        missing.append("案例")
    if not theories:
        missing.append("理论")
    if not methods:
        missing.append("方法")
    return {
        "status": "verified" if not missing else "partial",
        "missing": missing,
        "message": "本次方向已逐条对照本地知识库。" if not missing else "知识库未检索到匹配的" + "、".join(missing) + "依据；相关内容是通用设计建议，需后续核实。",
    }


def _unverified_direction_note() -> dict:
    return {
        "status": "unverified",
        "missing": ["逐条知识引用"],
        "message": "该建议未找到合适的本地知识库依据，需要后续核实。它仅作为通用设计建议，不视为借鉴本地案例、理论或方法。",
    }


def _grounded_fallback_directions(cases: list[dict], theories: list[dict], methods: list[dict],
                                  user_task: str, project_type: str, design_context: dict | None = None) -> dict:
    """Use only retrieved sources when the model output cannot be cited safely."""
    if not (cases and theories and methods):
        result = _fallback_directions(cases, user_task, project_type, design_context)
        result.update({
            "retrieved_theories": theories,
            "retrieved_methods": methods,
            "knowledge_note": _unverified_direction_note(),
        })
        return result

    result = _fallback_directions(cases, user_task, project_type, design_context)
    for index, direction in enumerate(result["directions"]):
        case = cases[index % len(cases)]
        theory = theories[index % len(theories)]
        method = methods[index % len(methods)]
        direction["cases"] = [case.get("name", "")]
        direction["evidence"] = {
            "case": {
                "name": case.get("name", ""),
                "strategy": case.get("strategy", ""),
                "source_text": case.get("content", ""),
                "why": f"参考“{case.get('strategy', '空间组织')}”这一已检索案例策略，校验本方向的空间组织。",
                "fit": {
                    "project_type": 0, "scale": 0, "function": 0, "site_climate": 0,
                    "average": 0,
                    "transferable": case.get("strategy", ""),
                    "not_copy": "尚未完成项目适配判断，不能直接照搬案例形式。",
                    "risk": "需要学生和导师进一步核实适用性。",
                },
            },
            "theory": {
                "name": theory.get("name", ""),
                "source_text": theory.get("content", ""),
                "why": f"用“{theory.get('name', '')}”检视方向是否回应场地、使用与体验。",
            },
            "method": {
                "name": method.get("name", ""),
                "source_text": method.get("content", ""),
                "why": f"将“{method.get('name', '')}”作为可执行的空间操作手段。",
            },
        }
        direction["evidence_status"] = "partial"
    result.update({
        "retrieved_theories": theories,
        "retrieved_methods": methods,
        "knowledge_note": {
            "status": "partial",
            "missing": ["项目适配判断"],
            "message": "知识来源真实，但模型输出未通过完整适配校验；只能作为待核实启发。",
        },
    })
    return result


def propose_directions(user_task: str, task_analysis: dict | None = None, answers: list[str] | None = None,
                       design_context: dict | None = None) -> dict:
    """基于任务 + 案例检索，提出 3 个设计方向。

    Args:
        user_task: 用户设计任务
        task_analysis: analyze_task 的输出（可省略，内部会重新分析）
        answers: 学生对设计导师问题的回答（可省略；提供则方向会贴合学生偏好）
        design_context: 设计讨论层形成的设计认知（意图/关注点/限制）

    Returns:
        {"directions": [...3个方向...]}
    """
    default = {"directions": []}

    # 1. 任务分析（若未提供）
    if task_analysis is None:
        task_analysis = analyze_task(user_task)

    # 2. 本地知识检索：案例、理论、方法都进入可核查的依据链。
    search_query = build_search_query(task_analysis)
    cases = case_search(search_query, 5).get("results", [])
    theories = theory_search(search_query, 3).get("results", [])
    methods = method_search(search_query, 3).get("results", [])
    cases, theories, methods = _filter_relevant_knowledge(cases, theories, methods)
    knowledge_note = _knowledge_note(cases, theories, methods)

    # 3. 构造提案输入
    context = {
        "user_task": user_task,
        "task_analysis": task_analysis,
        "retrieved_cases": [
            {"name": c.get("name"), "strategy": c.get("strategy"), "content": c.get("content", "")[:150]}
            for c in cases
        ],
        "retrieved_theories": [
            {"name": item.get("name"), "content": item.get("content", "")[:150]}
            for item in theories
        ],
        "retrieved_methods": [
            {"name": item.get("name"), "content": item.get("content", "")[:150]}
            for item in methods
        ],
    }
    # 设计讨论形成的认知注入（若有）
    if design_context:
        context["design_context"] = {
            "project_type": design_context.get("project_type", ""),
            "user_intention": design_context.get("user", "") or design_context.get("user_intention", ""),
            "site": design_context.get("site", ""),
            "goal": design_context.get("goal", ""),
            "constraint": design_context.get("constraint", ""),
            "design_intent": design_context.get("design_intent", ""),
            "key_focus": design_context.get("key_focus", []),
            "avoid": design_context.get("avoid", []),
            "understanding_summary": design_context.get("understanding_summary", ""),
        }

    if not DEEPSEEK_API_KEY:
        # 降级：基于检索结果简单构造 3 个方向
        return _grounded_fallback_directions(
            cases, theories, methods, user_task,
            context.get("design_context", {}).get("project_type", ""), context.get("design_context", {}),
        )

    try:
        resp = requests.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": "deepseek-chat",
                "messages": [
                    {"role": "system", "content": PROPOSER_PROMPT},
                    {"role": "user", "content": json.dumps(context, ensure_ascii=False)},
                ],
                "temperature": 0.3,
                "max_tokens": 1500,
            },
            timeout=90,
        )
        resp.raise_for_status()
        result = _extract_json(resp.json()["choices"][0]["message"]["content"])
        dirs = result.get("directions", [])
        project_type = context.get("design_context", {}).get("project_type", "")
        if len(dirs) >= 3 and _directions_match_project(dirs[:3], project_type) and _validate_direction_evidence(dirs[:3], cases, theories, methods):
            final_dirs = [_verified_evidence(direction, cases, theories, methods) for direction in dirs[:3]]
            all_fitted = all(direction.get("evidence_status") == "verified" for direction in final_dirs)
            final_note = knowledge_note if all_fitted else {
                "status": "partial",
                "missing": ["部分案例适配判断"],
                "message": "知识来源已经核验，但部分案例与当前项目的适配度不足或边界不完整，请按卡片风险谨慎迁移。",
            }
            adjustment_note = ""
            if answers and any(a and a.strip() for a in answers):
                adjustment_note = "已将最新对话补充并入设计意图，重新生成方向。"
            return {
                "core_conflict": result.get("core_conflict", ""),
                "key_questions": result.get("key_questions", []),
                "directions": final_dirs,
                "retrieved_cases": cases,
                "retrieved_theories": theories,
                "retrieved_methods": methods,
                "knowledge_note": final_note,
                "task_analysis": task_analysis,
                "adjustment_note": adjustment_note,
            }
        return _grounded_fallback_directions(cases, theories, methods, user_task, project_type, context.get("design_context", {}))
    except Exception as e:
        print(f"[direction_proposer] 提案失败: {e}")
        return _grounded_fallback_directions(
            cases, theories, methods, user_task,
            context.get("design_context", {}).get("project_type", ""), context.get("design_context", {}),
        )


def _directions_match_project(directions: list[dict], project_type: str) -> bool:
    """Ensure generated directions explicitly retain the confirmed project type."""
    if not project_type:
        return True
    text = " ".join(
        " ".join(str(direction.get(key, "")) for key in ("name", "core_strategy", "suitable_for", "description"))
        for direction in directions[:3]
    )
    if not any(term in project_type for term in ("学校", "校园", "教学")) and any(term in text for term in ("校园", "学生", "学习区")):
        return False
    matched = sum(
        project_type in " ".join(str(direction.get(key, "")) for key in ("name", "core_strategy", "suitable_for", "description"))
        for direction in directions[:3]
    )
    return matched >= 2


def _fallback_directions(cases: list[dict], user_task: str = "", project_type: str = "", design_context: dict | None = None) -> dict:
    """降级方案：基于检索案例构造 3 个方向（不依赖 LLM）。"""
    if "住宅" in user_task:
        return {
            "core_conflict": "在有限面积里，让住宅既回应乡村日常生活，也建立与道路和田野的舒适关系。",
            "key_questions": [
                "人从路边进入住宅时，如何兼顾私密与欢迎感？",
                "起居、用餐和卧室如何适应家庭一天的节奏？",
                "平原的风、日照和视野如何变成生活的一部分？",
            ],
            "directions": [
                {
                    "name": "院落日常型",
                    "core_strategy": "用半围合院落串起起居、餐厨和户外活动，把院子变成家庭的日常客厅。",
                    "strategy": ["围合院落", "室内外过渡"],
                    "suitable_for": "重视家庭活动与私密性",
                    "risk": "院落比例处理不好会压缩室内采光。",
                    "cases": [],
                    "description": "以院落作为采光、通风和日常停留的核心，卧室退到更安静的一侧。",
                },
                {
                    "name": "临路开合型",
                    "core_strategy": "沿道路设置缓冲前院和入口灰空间，住宅向田野打开、向道路保持适度收束。",
                    "strategy": ["前院缓冲", "界面开合"],
                    "suitable_for": "临路且需要兼顾来访",
                    "risk": "入口和车行组织不清会干扰室内安静。",
                    "cases": [],
                    "description": "把临路一侧处理成可停靠、可接待的前场，主要生活空间转向更开阔的景观面。",
                },
                {
                    "name": "平原观景型",
                    "core_strategy": "用连续屋檐、框景开口和通透公共空间，把平原的日照、风和远景引入日常起居。",
                    "strategy": ["连续屋檐", "框景采光"],
                    "suitable_for": "视野开阔的平原场地",
                    "risk": "大面积开口需要同步解决夏季遮阳与冬季保温。",
                    "cases": [],
                    "description": "将客厅、餐厅和露台连成一条面向景观的生活带，私密房间作为更稳定的背景。",
                },
            ],
            "retrieved_cases": cases,
        }

    if "办公" in user_task or "写字楼" in user_task:
        return {
            "core_conflict": "在临城市主干道的办公楼中，既要保证日常办公的效率与安静，又要承接会议、展示与对外接待。",
            "key_questions": [
                "会议与展示人流如何不打扰日常办公区？",
                "面向主干道的形象界面如何兼顾遮阳、降噪与采光？",
                "会议、展示和协作空间如何随使用规模灵活转换？",
            ],
            "directions": [
                {"name": "高效协同型", "core_strategy": "以办公楼的内部协作为核心，用清晰的办公组团、中庭交流带与共享会议点串联日常工作。", "strategy": ["办公组团", "协作中心"], "suitable_for": "重视部门协作与日常效率的企业", "risk": "如果共享区尺度过大，可能挤压专注办公面积。", "cases": []},
                {"name": "城市客厅型", "core_strategy": "将靠主干道的底层布置为接待、展示与路演空间，上部办公区保持独立、高效的工作秩序。", "strategy": ["首层展示", "对外接待"], "suitable_for": "需要展示企业形象并经常接待客户的办公楼", "risk": "对外人流需要与内部办公动线分流。", "cases": []},
                {"name": "弹性会议型", "core_strategy": "用可合可分的会议单元、共享支持空间与连续步道，让办公、会议和展示根据人数切换。", "strategy": ["可变会议", "共享支持"], "suitable_for": "会议、客户活动频率较高的团队", "risk": "可变隔断与设备系统需要提前控制成本与运维。", "cases": []},
            ],
            "retrieved_cases": cases,
        }

    if project_type:
        context = design_context or {}
        site = context.get("site", "场地条件")
        intent = context.get("design_intent", "学生确认的设计意图")
        return {
            "core_conflict": f"让{project_type}回应{site}，同时把“{intent}”落实为可使用的空间。",
            "key_questions": [
                f"{project_type}最核心的使用活动怎样形成清晰秩序？",
                f"场地的{site}怎样成为空间组织的依据？",
                f"怎样让“{intent}”不只停留在概念，而进入动线、界面和停留空间？",
            ],
            "directions": [
                {"name": "核心活动型", "core_strategy": f"以{project_type}的核心活动为主线组织入口、主要空间和支持空间，让“{intent}”落实在最常使用的场所。", "strategy": ["功能组织", "活动主线"], "suitable_for": project_type, "risk": "过度强调主功能时，需防止配套空间被压缩。", "cases": []},
                {"name": "场地回应型", "core_strategy": f"让{project_type}顺应{site}的到达、视线和环境条件，以空间开合回应“{intent}”。", "strategy": ["场地关系", "空间开合"], "suitable_for": project_type, "risk": "需要平衡场地表达与日常使用效率。", "cases": []},
                {"name": "体验节奏型", "core_strategy": f"通过从入口到核心空间的节奏变化，为{project_type}建立“{intent}”所需的停留与转换体验。", "strategy": ["动线节奏", "体验节点"], "suitable_for": project_type, "risk": "体验节点过多会削弱动线的清晰度。", "cases": []},
            ],
            "retrieved_cases": cases,
        }

    defaults = ["光之教堂", "萨伏伊别墅", "巴塞罗那德国馆"]
    names = [c.get("name", "") for c in cases[:3] if c.get("name")]
    names.extend(defaults[len(names):])
    return {
        "core_conflict": "先确定公共交流是以空间体验、开放共享，还是自然环境作为主导。",
        "key_questions": [
            "哪些空间需要让学生愿意停下来？",
            "开放交流与安静学习如何互不干扰？",
            "场地中最值得保留和回应的条件是什么？",
        ],
        "directions": [
            {"name": "空间体验型", "core_strategy": "用压缩-释放的空间序列和自然光，组织从经过到停留的体验。", "strategy": ["压缩-释放", "光环境"], "suitable_for": "需要形成记忆点的场地", "risk": "交流空间可能被过强的仪式感削弱。", "cases": [names[0]], "description": "以入口收束、中心释放和光环境变化组织体验，让公共活动在行进中自然发生。"},
            {"name": "开放共享型", "core_strategy": "用可穿行的公共界面和可变家具，把交通空间转成交流空间。", "strategy": ["底层架空", "流动空间"], "suitable_for": "人流汇集的校园节点", "risk": "开放过度时，安静学习区会受干扰。", "cases": [names[1]], "description": "以连续公共界面串联展览、讨论和休憩，让不同规模的交流可以随时发生。"},
            {"name": "自然融合型", "core_strategy": "用庭院、框景和半室外灰空间，让活动围绕可感知的自然展开。", "strategy": ["庭院", "框景借景"], "suitable_for": "有绿化或景观条件的场地", "risk": "空间过于分散时，核心交流氛围会变弱。", "cases": [names[2]], "description": "把庭院和半室外空间作为共享客厅，通过视线、风和光连接室内外活动。"},
        ],
        "retrieved_cases": cases,
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="ArchAI 设计方向提案测试")
    parser.add_argument("query", nargs="?", default="", help="用户设计任务")
    args = parser.parse_args()

    if not args.query:
        print("用法: python direction_proposer.py <用户任务>")
        sys.exit(1)

    print("提案中...")
    result = propose_directions(args.query)
    for i, d in enumerate(result["directions"], 1):
        print(f"\n方向{i}: {d['name']}")
        print(f"  策略: {d['strategy']}")
        print(f"  案例: {d['cases']}")
        print(f"  描述: {d['description'][:80]}...")
