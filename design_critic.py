"""
design_critic.py — ArchAI 方案评审智能体（Design Critic Agent）

模拟建筑评图老师，对 Generator 生成的方案进行专业评审。
这是 ArchAI 从"Agent 能运行"到"建筑设计智能体"的关键一步：
    Generator → Critic（评审）→ Revision Generator（优化）→ Final Proposal

Critic 检查四个维度：
    ① 基地响应检查 — 方案是否回应基地条件
    ② 案例迁移检查 — 是否真正使用了案例策略（而非仅引用名字）
    ③ 理论一致性检查 — 是否贯彻了引用的理论
    ④ 建筑合理性检查 — 面积/功能/流线/尺度

输出：
    {
      "score": 85,
      "strengths": ["..."],
      "problems": ["..."],
      "revision": ["..."],
      "details": {...}
    }
"""

import io
import json
import re
import sys
from pathlib import Path

import requests

BASE = Path(__file__).resolve().parent

CRITIC_PROMPT = """你是 ArchAI 的建筑方案评审老师（Design Critic）。
你模拟建筑评图老师，对 AI 生成的建筑设计方案进行专业评审。

评审前先理解任务背景和工具检索到的知识，然后从四个维度检查：

① 基地响应检查
方案是否回应了基地条件（周边关系、人流、朝向、场地限制）？

② 案例迁移检查（最重要的特色）
检查方案是否真正使用了案例策略，而非仅引用案例名字。
例如方案说"参考克朗楼"，检查克朗楼的核心策略（底层架空形成公共交流空间）
是否真的体现在方案里（如首层架空广场）。

③ 理论一致性检查
检查方案是否贯彻了引用的理论。
如方案引用"空间序列理论"，检查是否有：入口→过渡→核心空间→停留的序列。

④ 建筑合理性检查
检查面积分配、功能关系、流线组织、空间尺度的合理性。

输出 JSON（不要其他文字）。除总体结论外，必须提供八项结构化评图；每项引用方案原文，缺少依据时标记“无法判断”：
{
  "score": 0-100的整数,
  "strengths": ["2-4条优点"],
  "problems": ["2-4条不足"],
  "revision": ["2-4条修改建议，要具体可执行"],
  "criteria": {
    "requirement_response": {"score": 0, "status": "已经解决/部分解决/尚未解决/无法判断", "evidence": "方案原文", "comment": "判断"},
    "site_response": {"score": 0, "status": "...", "evidence": "...", "comment": "..."},
    "function_flow": {"score": 0, "status": "...", "evidence": "...", "comment": "..."},
    "spatial_experience": {"score": 0, "status": "...", "evidence": "...", "comment": "..."},
    "architectural_scale": {"score": 0, "status": "...", "evidence": "...", "comment": "..."},
    "constructability": {"score": 0, "status": "...", "evidence": "...", "comment": "..."},
    "knowledge_transfer": {"score": 0, "status": "...", "evidence": "...", "comment": "..."},
    "student_intent": {"score": 0, "status": "...", "evidence": "...", "comment": "..."}
  },
  "details": {
    "site_response": "基地响应检查结论",
    "case_transfer": "案例迁移检查结论",
    "theory_consistency": "理论一致性检查结论",
    "architectural_logic": "建筑合理性检查结论"
  }
}
评分参考：90+ 优秀可深化；75-89 良好需局部调整；60-74 及格需较大修改；<60 概念需重做。"""


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


def load_env() -> dict:
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


ENV = load_env()
DEEPSEEK_API_KEY = ENV.get("DEEPSEEK_API_KEY", "")

CRITIC_CRITERIA = (
    "requirement_response", "site_response", "function_flow", "spatial_experience",
    "architectural_scale", "constructability", "knowledge_transfer", "student_intent",
)


def _normalize_critic(result: dict) -> dict:
    normalized = dict(result or {})
    criteria = normalized.get("criteria") if isinstance(normalized.get("criteria"), dict) else {}
    allowed_status = {"已经解决", "部分解决", "尚未解决", "无法判断"}
    clean = {}
    for key in CRITIC_CRITERIA:
        item = criteria.get(key) if isinstance(criteria.get(key), dict) else {}
        try:
            score = max(0, min(100, int(item.get("score", 0))))
        except (TypeError, ValueError):
            score = 0
        clean[key] = {
            "score": score,
            "status": item.get("status") if item.get("status") in allowed_status else "无法判断",
            "evidence": str(item.get("evidence", "")).strip(),
            "comment": str(item.get("comment", "")).strip(),
        }
    normalized["criteria"] = clean
    return normalized


def critique(
    user_task: str,
    draft_solution: str,
    tool_result: dict | None = None,
    task_analysis: dict | None = None,
) -> dict:
    """评审一个设计方案。

    Args:
        user_task: 用户原始设计任务
        draft_solution: Generator 生成的方案文本
        tool_result: 工具检索结果（供检查案例迁移是否真实）
        task_analysis: 任务分析结果（供检查基地响应）

    Returns:
        评审 JSON：score/strengths/problems/revision/details
    """
    default = {
        "score": 70,
        "strengths": ["方案结构完整"],
        "problems": ["（评审失败，请人工检查）"],
        "revision": ["（评审失败）"],
        "details": {},
        "criteria": {},
    }

    if not DEEPSEEK_API_KEY:
        return _normalize_critic(default)

    # 构造评审输入：任务 + 工具知识 + 方案
    context = {
        "user_task": user_task,
        "task_analysis": task_analysis or {},
        "tool_knowledge": tool_result or {},
        "draft_solution": draft_solution,
    }

    try:
        resp = requests.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": "deepseek-chat",
                "messages": [
                    {"role": "system", "content": CRITIC_PROMPT},
                    {"role": "user", "content": json.dumps(context, ensure_ascii=False)},
                ],
                "temperature": 0.2,
                "max_tokens": 1500,
            },
            timeout=120,
        )
        resp.raise_for_status()
        result = _extract_json(resp.json()["choices"][0]["message"]["content"])
        # 保证字段完整
        for k, v in default.items():
            if k not in result or result[k] is None:
                result[k] = v
        return _normalize_critic(result)
    except Exception as e:
        print(f"[design_critic] 评审失败: {e}")
        return _normalize_critic(default)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="ArchAI 方案评审测试")
    parser.add_argument("--task", default="", help="用户任务")
    parser.add_argument("--draft", default="", help="方案文件路径或文本")
    args = parser.parse_args()

    if args.draft and Path(args.draft).exists():
        draft = Path(args.draft).read_text(encoding="utf-8")
    else:
        draft = args.draft

    if not draft:
        print("用法: python design_critic.py --task <任务> --draft <方案文本或文件>")
        sys.exit(1)

    print("评审中...")
    result = critique(args.task, draft)
    print(json.dumps(result, ensure_ascii=False, indent=2))


# ══════════════════════════════════════════════════════════════════
# Revision Generator（方案优化层）
# 根据 Critic 的评审意见，优化生成最终方案
# ══════════════════════════════════════════════════════════════════

REVISION_PROMPT = """你是 ArchAI 的方案优化设计师（Revision Generator）。

你收到：
1. 用户的设计任务
2. 初版方案（Generator 生成）
3. 评审意见（Design Critic 的评审结果：score/strengths/problems/revision）
4. 学生的反馈意见（可能为空，为空则仅按评审优化）

你的任务：针对评审的"不足""修改建议"和"学生反馈"，优化初版方案，生成优化后的完整方案。

规则：
- 保留初版的优点（strengths 里提到的不要破坏）
- 逐条回应 revision 建议和学生反馈，让修改"可见"
- 学生反馈优先级最高（如学生说"更开放"，优先满足学生）
- 输出完整方案（与初版同样结构），不是只写修改说明
- 在方案末尾加一节【优化说明】：逐条说明"针对评审意见/学生反馈做了哪些修改"

只输出优化后的方案 Markdown，不要其他解释。"""


REVISION_WITH_DIFF_PROMPT = """你是 ArchAI 的方案优化设计师（Revision Generator）。

你收到：
1. 用户的设计任务
2. 当前方案（学生正在看的版本）
3. 学生的反馈意见（"更开放""加入庭院"等）
4. 评审意见（可空）

你的任务：根据学生反馈，生成**优化后的方案**，并给出**清晰的改动对比**，让学生知道"改了什么、为什么改、改后有什么不同"。

输出 JSON（不要其他文字）：
{
  "revised_plan": "优化后的完整方案 Markdown（含【优化说明】节）",
  "diff_summary": {
    "feedback_response": "一句话：学生的反馈被如何理解和落实了",
    "changes": [
      {
        "what": "改了哪里（如：入口空间）",
        "from": "改前是什么（简短）",
        "to": "改后是什么（简短）",
        "why": "为什么这样改"
      },
      ...2-4条
    ],
    "kept": ["保留的内容"],
    "removed": ["删除的内容"]
  },
  "evidence_changes": {
    "kept": ["继续有效的知识依据"],
    "added": ["新增知识依据；没有则为空"],
    "invalidated": ["因修改而失效的旧依据；没有则为空"]
  }
}
不得擅自改变已确认的项目类型、使用者、场地和核心设计目标。没有新的检索结果时，不得编造新增知识依据。"""


def revise_with_diff(
    user_task: str,
    current_solution: str,
    user_feedback: str,
    review: dict | None = None,
    version_number: int = 2,
    selected_direction: dict | None = None,
    parent_version: int = 1,
) -> dict:
    """根据学生反馈优化方案，并返回结构化对比。

    Returns:
        {
            "revised_plan": 优化后方案 Markdown,
            "diff_summary": {"feedback_response", "changes": [{what, from, to, why}]}
        }
    """
    context = {
        "user_task": user_task,
        "current_solution": current_solution,
        "user_feedback": user_feedback,
        "review": review or {},
        "selected_direction": selected_direction or {},
        "knowledge_evidence": (selected_direction or {}).get("evidence", {}),
    }
    try:
        resp = requests.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": "deepseek-chat",
                "messages": [
                    {"role": "system", "content": REVISION_WITH_DIFF_PROMPT},
                    {"role": "user", "content": json.dumps(context, ensure_ascii=False)},
                ],
                "temperature": 0.3,
                "max_tokens": 4096,
            },
            timeout=180,
        )
        resp.raise_for_status()
        result = _extract_json(resp.json()["choices"][0]["message"]["content"])
        plan = result.get("revised_plan", "")
        # 清理 markdown 包裹
        if plan.startswith("```markdown"):
            plan = plan[len("```markdown"):].strip()
        elif plan.startswith("```"):
            plan = plan[3:].strip()
        if plan.endswith("```"):
            plan = plan[:-3].strip()
        if not plan:
            empty_diff = {
                "feedback_response": "模型未返回完整的新方案，已保留上一版方案，未将空结果展示为更新。",
                "changes": [], "kept": [], "removed": [],
            }
            return {
                "revised_plan": current_solution,
                "diff_summary": empty_diff,
                "evidence_changes": {"kept": [], "added": [], "invalidated": []},
                "version": _version_record(version_number, selected_direction, user_feedback, empty_diff, {}, parent_version),
            }
        diff = result.get("diff_summary", {"feedback_response": "", "changes": [], "kept": [], "removed": []})
        evidence_changes = result.get("evidence_changes", {"kept": [], "added": [], "invalidated": []})
        return {
            "revised_plan": plan,
            "diff_summary": diff,
            "evidence_changes": evidence_changes,
            "version": _version_record(version_number, selected_direction, user_feedback, diff, evidence_changes, parent_version),
        }
    except Exception as e:
        failed_diff = {"feedback_response": f"优化失败，已保留上一版：{e}", "changes": [], "kept": [], "removed": []}
        return {
            "revised_plan": current_solution,
            "diff_summary": failed_diff,
            "evidence_changes": {"kept": [], "added": [], "invalidated": []},
            "version": _version_record(version_number, selected_direction, user_feedback, failed_diff, {}, parent_version),
        }


def _version_record(number: int, selected_direction: dict | None, feedback: str,
                    diff_summary: dict, evidence_changes: dict, parent_version: int = 0) -> dict:
    direction = selected_direction or {}
    return {
        "number": number,
        "parent_version": parent_version,
        "direction": direction.get("name", ""),
        "feedback": feedback,
        "kept": diff_summary.get("kept", []) if isinstance(diff_summary, dict) else [],
        "removed": diff_summary.get("removed", []) if isinstance(diff_summary, dict) else [],
        "knowledge_evidence": direction.get("evidence", {}),
        "evidence_changes": evidence_changes if isinstance(evidence_changes, dict) else {},
    }


def revise(
    user_task: str,
    draft_solution: str,
    review: dict,
    tool_result: dict | None = None,
    user_feedback: str = "",
) -> str:
    """根据评审意见 + 学生反馈优化方案。

    Args:
        user_task: 用户原始任务
        draft_solution: 初版方案
        review: critique() 的输出
        tool_result: 工具检索结果（供参考）
        user_feedback: 学生的自由反馈意见（如"希望更开放""加入文化元素"）

    Returns:
        优化后的完整方案 Markdown
    """
    context = {
        "user_task": user_task,
        "draft_solution": draft_solution,
        "review": review,
        "user_feedback": user_feedback,
        "tool_knowledge": tool_result or {},
    }
    try:
        resp = requests.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": "deepseek-chat",
                "messages": [
                    {"role": "system", "content": REVISION_PROMPT},
                    {"role": "user", "content": json.dumps(context, ensure_ascii=False)},
                ],
                "temperature": 0.3,
                "max_tokens": 4096,
            },
            timeout=180,
        )
        resp.raise_for_status()
        revised = resp.json()["choices"][0]["message"]["content"]
        # 清理 markdown 包裹
        if revised.startswith("```markdown"):
            revised = revised[len("```markdown"):].strip()
        elif revised.startswith("```"):
            revised = revised[3:].strip()
        if revised.endswith("```"):
            revised = revised[:-3].strip()
        return revised
    except Exception as e:
        return f"⚠️ 方案优化失败: {e}"


def full_design_loop(user_task: str, tool_result: dict | None = None, task_analysis: dict | None = None,
                     user_choice: dict | None = None, directions: list[dict] | None = None,
                     design_context: dict | None = None) -> dict:
    """完整设计循环：初稿 → 评审 → 优化。

    Args:
        user_task: 用户任务
        tool_result: 工具检索结果（Generator 已产出的）
        task_analysis: 任务分析结果
        user_choice: 用户方向选择（Human-in-the-loop）
            {"direction_index": 0/1/2, "supplement": "补充要求"}
        directions: 方向提案结果（direction_proposer 的输出）

    Returns:
        {
            "task_analysis": {...},
            "retrieved_cases": [...],
            "initial_proposal": 初稿,
            "critic": {...},
            "revision": 优化稿,
            "design_directions": [...],   # 若提案了方向
            "user_choice": {...},         # 若用户选择了
        }
    """
    from generator import agent_generate

    facts = {
        key: str((design_context or {}).get(key, "")).strip()
        for key in ("project_type", "user", "site", "goal", "constraint", "design_intent")
    }
    fact_lines = [f"{key}: {value}" for key, value in facts.items() if value]
    effective_task = user_task
    if fact_lines:
        effective_task += "\n\n[已确认的设计事实]\n" + "\n".join(fact_lines)

    # 1. 初版生成（若用户选了方向，按方向生成）
    gen = agent_generate(effective_task, user_choice=user_choice, directions=directions)
    draft = gen.get("answer", "")
    tool_result = tool_result or gen.get("tool_result")
    task_analysis = task_analysis or gen.get("task_analysis")

    # 2. 评审
    review = critique(effective_task, draft, tool_result, task_analysis)

    # 3. 优化
    revised = revise(effective_task, draft, review, tool_result)
    selected_direction = {}
    if directions and user_choice:
        index = user_choice.get("direction_index", 0)
        if isinstance(index, int) and 0 <= index < len(directions):
            selected_direction = directions[index]
    version = {
        "number": 1,
        "direction": selected_direction.get("name", ""),
        "feedback": "",
        "kept": [],
        "removed": [],
        "knowledge_evidence": selected_direction.get("evidence", {}),
        "evidence_changes": {"kept": [], "added": [], "invalidated": []},
    }

    # 统一输出结构（供 UI 展示）
    return {
        "task_analysis": task_analysis or {},
        "tool_decision": gen.get("tool_decision") or {},
        "selected_tools": list((gen.get("tool_decision") or {}).keys()),
        "retrieved_cases": [
            {"name": c.get("name"), "strategy": c.get("strategy")}
            for c in (tool_result or {}).get("cases", [])
        ],
        "retrieved_theory": [
            {"name": t.get("name")} for t in (tool_result or {}).get("theory", [])
        ],
        "retrieved_methods": [
            {"name": m.get("name")} for m in (tool_result or {}).get("methods", [])
        ],
        "initial_proposal": draft,
        "critic": review,
        "revision": revised,
        "images": gen.get("images", []),
        "design_directions": directions or [],
        "user_choice": user_choice or {},
        "design_context": facts,
        "selected_direction": selected_direction,
        "version": version,
    }
