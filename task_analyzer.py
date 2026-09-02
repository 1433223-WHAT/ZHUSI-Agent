"""
task_analyzer.py — ArchAI 任务分析层（Task Analyzer）

作用：用户需求 → 结构化设计任务（Agent 的"大脑"第一步）。
这是 ArchAI 从 RAG 系统跨入 Agent 系统的桥梁。

输入：
    用户任务描述（如 "设计大学生服务中心，3000㎡，北食堂南教学楼"）

输出（JSON）：
    {
      "project_type": "校园公共建筑",
      "site_relationship": "连接教学生活两类人流",
      "design_intent": ["形成校园共享节点", "创造交流空间", "强化步行联系"],
      "design_questions": ["如何组织校园流线", "如何形成公共空间核心", "如何处理建筑开放界面"],
      "needed_tools": ["case_search", "theory_search", "method_search"]
    }

设计决策（用户拍板）：
- 用 DeepSeek LLM 分析（理解设计意图，而非关键词匹配）
- JSON 结构化输出
- 三个工具默认全开放（案例/理论/方法不是互斥的）
- 增加 design_intent 字段（建筑 AI 区分普通 AI 的关键）
"""

import io
import json
import os
import re
import sys
from pathlib import Path

import requests

BASE = Path(__file__).resolve().parent


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
DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1/chat/completions"
DEEPSEEK_MODEL = "deepseek-chat"

SYSTEM_PROMPT = """你是 ArchAI 建筑设计智能体的任务分析器。
你的职责：把用户的建筑设计需求，解析为结构化设计任务。

分析维度：
1. project_type — 建筑类型（如 校园公共建筑/纪念建筑/文化建筑/住宅）
2. site_relationship — 基地与周边的关系（如 连接教学生活两类人流/嵌入山体）
3. design_intent — 设计意图（3-5条，用户想达到的空间目标）
4. design_questions — 设计问题（3-5条，把意图转化为可检索的具体问题）
5. needed_tools — 需要调用的工具（默认三个都列：case_search, theory_search, method_search）

规则：
- design_questions 要具体到"如何…"，能被用于检索建筑案例/理论/方法
- 不要编造用户没提供的信息；信息不足时基于建筑常识合理推断
- 只输出 JSON，不要任何解释文字"""


def _extract_json(text: str) -> dict:
    """从 LLM 响应提取 JSON（处理可能的 markdown 代码块）。"""
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            pass
    raise ValueError(f"无法解析任务分析 JSON: {text[:200]}")


def analyze_task(user_input: str) -> dict:
    """核心函数：用户需求 → 结构化设计任务。

    Args:
        user_input: 用户任务描述

    Returns:
        结构化任务 JSON。LLM 失败时降级为简单结构（保证不崩）。
    """
    default = {
        "project_type": "公共建筑",
        "site_relationship": "",
        "design_intent": [],
        "design_questions": [user_input],
        "needed_tools": ["case_search", "theory_search", "method_search"],
    }

    if not DEEPSEEK_API_KEY:
        default["design_questions"] = [user_input]
        return default

    try:
        resp = requests.post(
            DEEPSEEK_BASE_URL,
            headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": DEEPSEEK_MODEL,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"用户需求：{user_input}"},
                ],
                "temperature": 0.2,
                "max_tokens": 1000,
            },
            timeout=60,
        )
        resp.raise_for_status()
        result = _extract_json(resp.json()["choices"][0]["message"]["content"])
        # 保证字段完整
        for k, v in default.items():
            result.setdefault(k, v)
        return result
    except Exception as e:
        print(f"[task_analyzer] LLM 分析失败，降级: {e}")
        default["design_questions"] = [user_input]
        return default


def build_search_query(task: dict) -> str:
    """把任务分析结果拼成检索 query（供三个工具用）。

    用 design_questions + design_intent，但控制长度（避免太长稀释语义）。
    只取核心短语，每个问题截断到关键部分。
    """
    parts = []
    # design_questions 是主要检索信号
    for q in task.get("design_questions", []):
        q = q.strip()
        if not q:
            continue
        # 去掉"如何…"前缀，保留核心；截断到 30 字
        core = re.sub(r"^(如何|怎么|怎样|怎样进行)\s*", "", q)
        if len(core) > 30:
            core = core[:30]
        parts.append(core)
    # design_intent 辅助（去重）
    seen = set(parts)
    for intent in task.get("design_intent", []):
        intent = intent.strip()
        if intent and intent not in seen:
            seen.add(intent)
            if len(parts) >= 6:  # 最多 6 个短语
                break
            parts.append(intent[:30])

    return " ".join(parts) if parts else "建筑设计"


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="ArchAI 任务分析器测试")
    parser.add_argument("query", nargs="?", default="", help="用户任务")
    args = parser.parse_args()

    if not args.query:
        print("用法: python task_analyzer.py <用户任务>")
        print("示例: python task_analyzer.py '设计大学生服务中心，3000㎡，北食堂南教学楼'")
        sys.exit(1)

    result = analyze_task(args.query)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print("\n检索 query:", build_search_query(result))
