"""
generator.py — ArchAI 生成层（Generation Layer）

把"任务分析 → 工具检索 → DeepSeek 生成"的完整链路封装为独立模块。
这是 B2 流程的固化版本，形成清晰的分层：
    ① task_analyzer（任务理解）
    ② agent_tools（知识工具）
    ③ generator（本文件，生成）
    ④ server.py（只做 HTTP 壳）

调用方式：
    from generator import agent_generate
    result = agent_generate("设计大学生服务中心，3000㎡")
"""

import io
import json
import os
import sys
from pathlib import Path

import requests

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))

from task_analyzer import analyze_task, build_search_query  # noqa: E402
from agent_tools import case_search, theory_search, method_search  # noqa: E402
from search_images import search_images  # noqa: E402

PROMPT_PATH = BASE / "prompts" / "archai_system_prompt_v2.4.txt"


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


def _fmt_dir_strategy(chosen: dict) -> str:
    """兼容方向字段：core_strategy（字符串）或 strategy（数组/字符串）。"""
    v = chosen.get("core_strategy") or chosen.get("strategy") or ""
    if isinstance(v, list):
        return "、".join(str(x) for x in v)
    return str(v)


def _load_v24_prompt() -> str:
    """旧生成链 system prompt。

    V1.2 起与筑思对话链隔离：不再要求"生成完整设计方案"（旧 ArchAI 哲学），
    改为筑思定位——按学生请求提供可修改的示范性设计骨架，保留学生决策权。
    """
    if PROMPT_PATH.exists():
        return PROMPT_PATH.read_text(encoding="utf-8")
    return (
        "你是筑思Agent，一名面向建筑专业学生的建筑学习与设计协作助手。\n"
        "学生明确请求设计/框架时，你有义务提供一版可修改、可放弃的示范性设计骨架"
        "（入口/公共区/借阅核心/自习阅览/儿童活动/交通关系的组织），并声明"
        "'可以接受、修改、组合或完全放弃'。骨架属于 AI 建议，不是学生已确认的决定。\n"
        "不替学生拍板：不把 AI 建议写成学生决定，不自动生成不可修改的完整方案。\n"
        "涉及建筑事实（建筑师/年代/尺寸/原文）只能依据检索到的知识，不得编造；"
        "没有合适知识时明确说明是通用设计推演，需后续核实。"
    )


def build_tool_message(query: str, tool_result: dict, images: list[dict]) -> str:
    """拼接用户消息：问题 + 三个工具的结构化返回 + 图片策略。"""
    cases = tool_result.get("cases", [])
    theory = tool_result.get("theory", [])
    methods = tool_result.get("methods", [])

    def fmt_cases():
        lines = []
        for c in cases:
            lines.append(f"- 案例《{c.get('name','')}》 | 策略: {c.get('strategy','')}")
            lines.append(f"  {c.get('content','')[:200]}")
        return "\n".join(lines) if lines else "（无匹配案例）"

    def fmt_theory():
        lines = []
        for t in theory:
            lines.append(f"- 理论《{t.get('name','')}》")
            lines.append(f"  {t.get('content','')[:200]}")
        return "\n".join(lines) if lines else "（无匹配理论）"

    def fmt_methods():
        lines = []
        for m in methods:
            lines.append(f"- 方法《{m.get('name','')}》")
            lines.append(f"  {m.get('content','')[:200]}")
        return "\n".join(lines) if lines else "（无匹配方法）"

    img_lines = []
    for i in images:
        caption = i.get("caption") or i.get("description") or i.get("filename", "")
        strat = i.get("spatial_strategy") or i.get("design_topics", [])[:2]
        img_lines.append(
            f"- [{i.get('case','')}] {caption} | 设计策略: {', '.join(strat)}"
        )
    img_block = "\n".join(img_lines) if img_lines else "（无匹配图片）"

    return f"""【用户问题】
{query}

【案例经验】（本地知识引擎 · 工具返回）
{fmt_cases()}

【理论依据】
{fmt_theory()}

【设计方法】
{fmt_methods()}

【相关案例图片及设计策略】
{img_block}

请基于以上工具检索结果，为用户的设计需求提供一版可修改、可放弃的示范性设计骨架。
设计依据应结合：案例佐证（谁这样做过）、理论支撑（为什么有效）、方法操作（具体怎么做）。
骨架属于 AI 建议，不是学生已确认的决定；必须声明"可以接受、修改、组合或完全放弃"。
如果用户的问题属于案例分析/策略迁移/案例比较，请按对应的输出模板回答。"""


def agent_generate(
    query: str,
    use_analyzer: bool = True,
    tool_decision: dict | None = None,
    user_choice: dict | None = None,
    directions: list[dict] | None = None,
) -> dict:
    """Agent 生成入口：任务分析 → 工具检索 → DeepSeek 生成。

    Args:
        query: 用户任务
        use_analyzer: True=B2（先 Task Analyzer 分析），False=B1（直接用原 query）
        tool_decision: 工具决策（Tool Router 输出），可控制调用哪些工具
            {"cases": bool, "theory": bool, "methods": bool}
            省略时默认三个都调。
        user_choice: 用户方向选择（Human-in-the-loop）
            {"direction_index": 0/1/2, "supplement": "补充要求"}
        directions: 方向提案结果（direction_proposer 的输出）

    Returns:
        {
            "images": [...],
            "answer": str,
            "tool_result": {...},
            "task_analysis": {...} | None,
        }
    """
    # 1. 图片检索
    try:
        images = search_images(query, 4)
    except Exception as e:
        images = [{"error": str(e)}]

    # 2. 任务分析 → 检索 query + 工具决策
    task_analysis = None
    search_query = query
    if use_analyzer:
        task_analysis = analyze_task(query)
        search_query = build_search_query(task_analysis)

    # 2.5 工具决策（Tool Router）：未指定时自动判断
    if tool_decision is None:
        from tool_router import decide_tools
        tool_decision = decide_tools(task_analysis, query)

    # 3. 工具检索（按 tool_decision 决定调哪些）
    decision = tool_decision or {"cases": True, "theory": True, "methods": True}
    tool_result = {}
    if decision.get("cases", True):
        tool_result["cases"] = case_search(search_query, 3).get("results", [])
    if decision.get("theory", True):
        tool_result["theory"] = theory_search(search_query, 2).get("results", [])
    if decision.get("methods", True):
        tool_result["methods"] = method_search(search_query, 3).get("results", [])

    # 4. 生成
    if not DEEPSEEK_API_KEY:
        return {"images": images, "answer": "⚠️ 服务端未配置 DEEPSEEK_API_KEY", "error": "missing key"}

    system_prompt = _load_v24_prompt()
    user_msg = build_tool_message(query, tool_result, images)

    # 4.5 用户方向选择注入（Human-in-the-loop）
    if user_choice and directions:
        chosen = directions[user_choice.get("direction_index", 0)] if directions else None
        if chosen:
            dir_block = (
                f"\n\n【学生选择的设计方向】\n"
                f"方向名称：{chosen.get('name', '')}\n"
                f"核心策略：{_fmt_dir_strategy(chosen)}\n"
                f"参考案例：{', '.join(chosen.get('cases', []))}\n"
                f"方向描述：{chosen.get('description', '')}"
            )
            if user_choice.get("supplement"):
                dir_block += f"\n\n【学生的补充要求】\n{user_choice['supplement']}"
            dir_block += "\n\n请严格按学生选择的方向生成方案，并在方案开头标注【设计方向】。"
            user_msg += dir_block

    headers = {"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_msg},
        ],
        "temperature": 0.4,
        "max_tokens": 4096,
    }
    try:
        resp = requests.post(DEEPSEEK_BASE_URL, headers=headers, json=payload, timeout=120)
        resp.raise_for_status()
        answer = resp.json()["choices"][0]["message"]["content"]
    except requests.exceptions.HTTPError as e:
        answer = f"⚠️ DeepSeek 调用失败: HTTP {e.response.status_code}: {e.response.text[:200]}"
    except Exception as e:
        answer = f"⚠️ DeepSeek 调用失败: {e}"

    return {
        "images": images,
        "answer": answer,
        "tool_result": tool_result,
        "task_analysis": task_analysis,
        "tool_decision": tool_decision,
        "user_choice": user_choice,
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="ArchAI 生成层测试")
    parser.add_argument("query", nargs="?", default="", help="用户任务")
    parser.add_argument("--no-analyzer", action="store_true", help="跳过任务分析（B1）")
    args = parser.parse_args()

    if not args.query:
        print("用法: python generator.py <用户任务> [--no-analyzer]")
        sys.exit(1)

    result = agent_generate(args.query, use_analyzer=not args.no_analyzer)
    print(f"\n答案: {len(result.get('answer', ''))} 字")
    print(result.get("answer", "")[:800])
