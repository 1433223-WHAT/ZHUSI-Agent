"""
agent_tools.py — ArchAI Agent 工具层

把本地知识引擎的三个检索能力封装成标准 Agent Tools。
每个工具带 Tool Schema（name/description/input/output），
供未来 Agent（任务分析 → 决定调用工具 → 获取知识 → 生成方案）调用。

工具清单：
1. case_search   — 根据设计问题找建筑案例策略
2. theory_search — 根据设计问题找理论依据
3. method_search — 根据设计问题找设计方法

与 local_search 的区别：
- local_search 一次返回三类（适合直接预览）
- agent_tools 一次调一个工具（适合 Agent 按需调用）
"""

import io
import json
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))

from local_search import local_retrieve  # noqa: E402


# ── 工具 Schema ──────────────────────────────────────────────────
# 每个工具给 Agent 看的是"能力描述"，不是实现细节

TOOL_SCHEMAS = [
    {
        "name": "case_search",
        "description": "根据设计问题寻找相关建筑案例的设计策略。返回案例名称、设计问题、核心方法、适用场景。",
        "input": "设计问题描述，如：空间体验、光环境、流线组织、材料表达、场地应对",
        "output": {
            "name": "案例名称（如 光之教堂）",
            "strategy": "该案例针对的设计策略",
            "content": "策略详细内容",
            "score": "相关度评分(0-1)",
        },
    },
    {
        "name": "theory_search",
        "description": "根据设计问题寻找支撑设计决策的建筑理论依据。返回理论名称与核心概念。",
        "input": "设计问题或设计手法，如：为什么光能产生精神体验、空间如何影响情绪",
        "output": {
            "name": "理论名称（如 建筑现象学）",
            "content": "理论核心概念",
            "score": "相关度评分(0-1)",
        },
    },
    {
        "name": "method_search",
        "description": "根据设计问题寻找可操作的设计方法。返回方法名称、核心逻辑、操作方式。",
        "input": "设计意图或操作手法，如：如何组织空间序列、如何引入自然光",
        "output": {
            "name": "方法名称（如 压缩-释放空间序列）",
            "content": "方法核心逻辑",
            "score": "相关度评分(0-1)",
        },
    },
]


# ── 工具实现 ────────────────────────────────────────────────────

def case_search(query: str, top_k: int = 3) -> dict:
    """案例检索工具：根据设计问题找建筑案例策略。

    优先返回核心手法（category=strategy）节点，
    避免"适用场景/设计问题"等低策略性节点占据结果。
    """
    result = local_retrieve(query, top_k, prefer_category="strategy")
    cases = result.get("cases", [])
    # 去重：同一案例保留最高分策略
    seen = {}
    for c in cases:
        name = c.get("name", "")
        if name not in seen or c.get("score", 0) > seen[name].get("score", 0):
            seen[name] = c
    return {
        "tool": "case_search",
        "query": query,
        "results": list(seen.values()),
    }


def theory_search(query: str, top_k: int = 2) -> dict:
    """理论检索工具：根据设计问题找理论依据。"""
    result = local_retrieve(query, top_k)
    return {
        "tool": "theory_search",
        "query": query,
        "results": result.get("theory", []),
    }


def method_search(query: str, top_k: int = 3) -> dict:
    """方法检索工具：根据设计问题找设计方法。"""
    result = local_retrieve(query, top_k)
    return {
        "tool": "method_search",
        "query": query,
        "results": result.get("methods", []),
    }


# ── 工具注册表 ──────────────────────────────────────────────────

TOOLS = {
    "case_search": case_search,
    "theory_search": theory_search,
    "method_search": method_search,
}


def get_tool_schemas() -> list[dict]:
    """返回所有工具的描述，供 Agent 系统提示词引用。"""
    return TOOL_SCHEMAS


def call_tool(name: str, query: str, top_k: int = 3) -> dict:
    """按名称调用工具。Agent 决策后调用此入口。"""
    if name not in TOOLS:
        return {"tool": name, "error": f"未知工具: {name}，可用: {list(TOOLS.keys())}"}
    return TOOLS[name](query, top_k)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="ArchAI Agent 工具测试")
    parser.add_argument("tool", nargs="?", default="case_search", help="工具名")
    parser.add_argument("query", nargs="?", default="", help="查询词")
    parser.add_argument("--top_k", type=int, default=3)
    parser.add_argument("--list", action="store_true", help="列出所有工具")
    args = parser.parse_args()

    if args.list:
        print("ArchAI Agent 工具清单:")
        for s in TOOL_SCHEMAS:
            print(f"  - {s['name']}: {s['description']}")
        sys.exit(0)

    if not args.query:
        print("用法: python agent_tools.py <tool> <query> [--top_k 3]")
        print("示例: python agent_tools.py case_search '如何利用自然光营造精神空间'")
        print("      python agent_tools.py --list")
        sys.exit(1)

    result = call_tool(args.tool, args.query, args.top_k)
    print(json.dumps(result, ensure_ascii=False, indent=2))
