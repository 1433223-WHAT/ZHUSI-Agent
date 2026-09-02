"""
tool_router.py — ArchAI 工具路由层（Tool Router V1）

作用：根据 Task Analyzer 的任务分析结果，决定调用哪些知识工具。
让 B2 从"固定调用三个工具"升级为"AI 自主选择工具"。

决策逻辑：
- 用户的 design_intent / design_questions 决定需要哪些知识
- 案例分析类 → 主要案例 + 理论
- 设计手法类 → 方法 + 案例
- 完整方案类 → 三者都调

架构位置：
    Task Analyzer → Tool Router → 工具调用 → Generator
"""

import io
import json
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

ROUTER_PROMPT = """你是 ArchAI 建筑设计智能体的工具路由器。
你的任务：根据任务分析结果，决定需要调用哪些知识工具。

可用工具：
- case_search: 查找建筑案例设计策略（需要"谁这样做过"时）
- theory_search: 查找理论依据（需要"为什么有效"时）
- method_search: 查找可操作设计方法（需要"怎么做"时）

判断规则：
- 案例分析/作品解读 → case_search + theory_search（以理解案例为主）
- 设计手法/方法询问 → method_search + case_search
- 完整方案设计 → 三者都要
- 比较案例 → case_search（可含 theory）

只输出 JSON：
{
  "cases": true/false,
  "theory": true/false,
  "methods": true/false,
  "reason": "一句话说明为什么这样选择"
}"""


def _extract_json(text: str) -> dict:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    import re
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


def decide_tools(task_analysis: dict | None, user_input: str) -> dict:
    """根据任务分析结果决定调用哪些工具。

    Args:
        task_analysis: analyze_task 的输出（可为 None）
        user_input: 用户原始输入

    Returns:
        {"cases": bool, "theory": bool, "methods": bool, "reason": str}
    """
    default = {"cases": True, "theory": True, "methods": True, "reason": "默认全调"}

    # 构造路由判断的输入
    context = {
        "project_type": (task_analysis or {}).get("project_type", ""),
        "design_intent": (task_analysis or {}).get("design_intent", []),
        "design_questions": (task_analysis or {}).get("design_questions", []),
        "user_input": user_input,
    }

    if not DEEPSEEK_API_KEY:
        return default

    try:
        resp = requests.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": "deepseek-chat",
                "messages": [
                    {"role": "system", "content": ROUTER_PROMPT},
                    {"role": "user", "content": json.dumps(context, ensure_ascii=False)},
                ],
                "temperature": 0.1,
                "max_tokens": 300,
            },
            timeout=60,
        )
        resp.raise_for_status()
        decision = _extract_json(resp.json()["choices"][0]["message"]["content"])
        result = {
            "cases": bool(decision.get("cases", True)),
            "theory": bool(decision.get("theory", True)),
            "methods": bool(decision.get("methods", True)),
            "reason": decision.get("reason", ""),
        }
        return result
    except Exception as e:
        print(f"[tool_router] LLM 路由失败，默认全调: {e}")
        return default


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="ArchAI 工具路由器测试")
    parser.add_argument("query", nargs="?", default="", help="用户任务")
    args = parser.parse_args()

    if not args.query:
        print("用法: python tool_router.py <用户任务>")
        sys.exit(1)

    from task_analyzer import analyze_task

    analysis = analyze_task(args.query)
    print("任务分析:", json.dumps(analysis, ensure_ascii=False)[:300])
    print()
    decision = decide_tools(analysis, args.query)
    print("工具决策:", json.dumps(decision, ensure_ascii=False, indent=2))
