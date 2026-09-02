"""
design_mentor.py — ArchAI 设计导师对话层（Human-in-the-loop 2.0）

在方向提案前，AI 像设计导师一样主动提问，理解学生的设计偏好。
学生可回答、可修改、可跳过。回答会调整方向提案。

流程：
    任务分析 → 【AI 主动提问】→ 学生回答/跳过 → 方向提案（带学生偏好）→ …

核心价值：从"菜单式点选"升级为"对话式推演"。
"""

import io
import json
import re
import sys
from pathlib import Path

import requests

BASE = Path(__file__).resolve().parent

MENTOR_ASK_PROMPT = """你是 ArchAI 建筑设计智能体的设计导师。
学生刚输入了一个设计任务。在给出方向建议前，判断是否需要先提问：
- 如果任务信息已足够支撑方向提案（项目类型、使用者、场地、目标中已有三项以上明确），或学生明确请求"帮我设计/给我一个框架/给我一个方案起点"，则不要提问，返回 questions 为空数组 []（skip=true）。
- 否则，像真实建筑导师一样，先问最关键的 1 个问题来理解学生的设计意图。

设计任务分析：
- 项目类型：{project_type}
- 设计意图：{design_intent}
- 设计问题：{design_questions}

你需要：
1. 判断这个任务最关键的"分岔问题"是什么（例如：更偏仪式感还是日常感？主要给谁用？空间更封闭还是开放？）
2. 用口语化、像导师聊天的方式提问，不要论文腔
3. 最多问 1 个问题，给出 2-3 个倾向选项，但也允许学生自由回答

输出 JSON（不要其他文字）：
{{
  "skip": true/false,
  "questions": [
    {{
      "question": "口语化问题",
      "options": ["倾向A", "倾向B", "倾向C"],
      "purpose": "这个问题影响什么（一句话）"
    }}
  ]
}}
skip=true 时 questions 必须为空数组。"""

MENTOR_ADJUST_PROMPT = """你是 ArchAI 建筑设计智能体的设计导师。
学生回答了你之前的问题，现在根据回答调整设计方向提案。

学生的回答：{answers}

当前拟提的方向：{directions}

你需要：
1. 根据学生的回答，调整方向（可能保留/修改/替换某个方向）
2. 学生的回答可能明显偏向某个方向，也可能提出新需求
3. 保持 3 个方向，差异化明显

输出 JSON（不要其他文字）：
{{
  "adjustment_note": "一句话说明你如何根据学生回答调整了方向",
  "directions": [
    {{
      "name": "方向名",
      "core_strategy": "一句话核心策略",
      "suitable_for": "适合场景",
      "cases": ["案例名"],
      "risk": "风险",
      "description": "120字内描述"
    }},
    ...3个
  ]
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


def mentor_ask(user_task: str, task_analysis: dict | None = None) -> dict:
    """AI 主动提问：基于任务分析，提出关键问题（信息足够时跳过）。

    Returns:
        {"questions": [{"question", "options", "purpose"}]}  —— 空数组表示无需提问，直接进入方向提案
    """
    from task_analyzer import analyze_task

    if task_analysis is None:
        task_analysis = analyze_task(user_task)

    if not DEEPSEEK_API_KEY:
        return {"questions": []}

    prompt = MENTOR_ASK_PROMPT.format(
        project_type=task_analysis.get("project_type", ""),
        design_intent="；".join(task_analysis.get("design_intent", []))[:200],
        design_questions="；".join(task_analysis.get("design_questions", []))[:300],
    )

    try:
        resp = requests.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": "deepseek-chat",
                "messages": [
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": f"设计任务：{user_task}"},
                ],
                "temperature": 0.3,
                "max_tokens": 800,
            },
            timeout=60,
        )
        resp.raise_for_status()
        result = _extract_json(resp.json()["choices"][0]["message"]["content"])
        if result.get("skip") is True:
            return {"questions": []}
        return {"questions": result.get("questions", [])[:1]}
    except Exception as e:
        print(f"[design_mentor] 提问失败: {e}")
        return {"questions": []}


def mentor_adjust(user_task: str, answers: list[str], directions: list[dict]) -> dict:
    """根据学生回答调整方向。

    Args:
        user_task: 设计任务
        answers: 学生对问题的回答（列表）
        directions: 原方向提案

    Returns:
        {"adjustment_note": str, "directions": [...]}
    """
    if not DEEPSEEK_API_KEY or not answers or not any(a.strip() for a in answers):
        return {"adjustment_note": "（学生跳过提问，方向未调整）", "directions": directions}

    prompt = MENTOR_ADJUST_PROMPT.format(
        answers="；".join(a for a in answers if a.strip()),
        directions=json.dumps(directions, ensure_ascii=False),
    )

    try:
        resp = requests.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": "deepseek-chat",
                "messages": [
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": f"设计任务：{user_task}"},
                ],
                "temperature": 0.3,
                "max_tokens": 1500,
            },
            timeout=60,
        )
        resp.raise_for_status()
        result = _extract_json(resp.json()["choices"][0]["message"]["content"])
        dirs = result.get("directions", [])
        if len(dirs) >= 3:
            return {
                "adjustment_note": result.get("adjustment_note", ""),
                "directions": dirs[:3],
            }
        return {"adjustment_note": "（方向调整失败，保持原方向）", "directions": directions}
    except Exception as e:
        print(f"[design_mentor] 调整失败: {e}")
        return {"adjustment_note": "（调整失败，保持原方向）", "directions": directions}


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="ArchAI 设计导师对话层测试")
    parser.add_argument("query", nargs="?", default="", help="设计任务")
    args = parser.parse_args()

    if not args.query:
        print("用法: python design_mentor.py <设计任务>")
        sys.exit(1)

    # 测试提问
    print("=== AI 主动提问 ===")
    result = mentor_ask(args.query)
    for i, q in enumerate(result.get("questions", []), 1):
        print(f"Q{i}: {q.get('question')}")
        print(f"   选项: {q.get('options')}")
        print(f"   目的: {q.get('purpose')}")
