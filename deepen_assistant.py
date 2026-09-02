"""
deepen_assistant.py — ArchAI 深化助手（Deepen Assistant）

第三层闭环：学生选择方向后，可针对具体方面继续深化。
关键定位：辅助判断，不是功能菜单。给策略建议 + 案例依据 + 设计提醒，不替学生画图。

深化维度（4 项）：
    light    — 光环境：如何强化空间情绪？
    material — 材料氛围：如何让空间更有纪念感/氛围感？
    sequence — 空间序列：如何设计进入-停留-离开的体验？
    behavior — 使用行为：如何让人与空间产生关系？

输出结构（每项深化）：
    current_strategy: 当前设计策略（基于初稿提炼）
    case_reference:   案例借鉴（检索到的相关案例 + 具体手法）
    suggestions:      可尝试的手法（3-4 条，具体可操作）
    reminder:         设计提醒（1 条，体现"辅助判断而非给答案"）
"""

import io
import json
import re
import sys
from pathlib import Path

import requests

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))

from agent_tools import case_search, theory_search, method_search  # noqa: E402

DEEPEN_DIMENSIONS = {
    "light": {
        "label": "💡 光环境",
        "question": "如何强化空间情绪？",
    },
    "material": {
        "label": "🧱 材料氛围",
        "question": "如何让空间更有纪念感/氛围感？",
    },
    "sequence": {
        "label": "🚶 空间序列",
        "question": "如何设计进入-停留-离开的体验？",
    },
    "behavior": {
        "label": "👥 使用行为",
        "question": "如何让人与空间产生关系？",
    },
}

DEEPEN_PROMPT = """你是 ArchAI 建筑设计智能体的深化助手。
学生已选定了设计方向，现在想针对某一个方面继续深化。你是辅助判断者，不是方案生成器。

你收到：
1. 设计任务
2. 学生选定的方向（方向名/核心策略/参考案例）
3. 深化维度（light/material/sequence/behavior）
4. 检索到的相关案例/理论/方法

你的输出（JSON，不要其他文字）：
{
  "current_strategy": "当前设计策略（一句话，基于方向的策略）",
  "case_reference": "案例借鉴（1-2句，说明参考哪个案例的什么手法，为什么）",
  "suggestions": ["可尝试的手法1（具体可操作）", "手法2", "手法3"],
  "reminder": "设计提醒（1句，提醒学生注意的平衡/风险，体现'辅助判断而非给答案'）"
}

语言要求：
- 简洁、行动导向，像导师在草图上改一笔时的叮嘱
- suggestions 要具体可执行（如"核心空间采用单一材料控制视觉噪音"），不是空泛理论
- reminder 必须是提醒性的（如"材料越纯粹，越需要控制尺度避免压迫感"），不是又一条建议"""


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


def deepen(
    user_task: str,
    direction: dict,
    dimension: str,
) -> dict:
    """深化助手：针对方向 + 维度，输出针对性建议。

    Args:
        user_task: 用户设计任务
        direction: 学生选定的方向（name/core_strategy/cases/description）
        dimension: light/material/sequence/behavior

    Returns:
        {
            "dimension": str,
            "dimension_label": str,
            "current_strategy": str,
            "case_reference": str,
            "suggestions": [str],
            "reminder": str,
        }
    """
    default = {
        "dimension": dimension,
        "dimension_label": DEEPEN_DIMENSIONS.get(dimension, {}).get("label", dimension),
        "current_strategy": (direction.get("core_strategy") or "")[:80],
        "case_reference": "（参考所选方向的案例）",
        "suggestions": ["（深化建议生成失败，请人工补充）"],
        "reminder": "（提醒生成失败）",
    }

    if dimension not in DEEPEN_DIMENSIONS:
        return default

    # 检索该维度的知识
    dim_query = DEEPEN_DIMENSIONS[dimension]["question"]
    search_q = f"{direction.get('core_strategy','')} {dim_query}"
    cases = case_search(search_q, 3).get("results", [])
    theory = theory_search(search_q, 1).get("results", [])
    methods = method_search(search_q, 3).get("results", [])

    if not DEEPSEEK_API_KEY:
        return default

    context = {
        "user_task": user_task,
        "direction": direction,
        "dimension": dimension,
        "dimension_question": DEEPEN_DIMENSIONS[dimension]["question"],
        "retrieved_cases": [
            {"name": c.get("name"), "strategy": c.get("strategy")}
            for c in cases
        ],
        "retrieved_theory": [{"name": t.get("name")} for t in theory],
        "retrieved_methods": [{"name": m.get("name")} for m in methods],
    }

    try:
        resp = requests.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": "deepseek-chat",
                "messages": [
                    {"role": "system", "content": DEEPEN_PROMPT},
                    {"role": "user", "content": json.dumps(context, ensure_ascii=False)},
                ],
                "temperature": 0.3,
                "max_tokens": 800,
            },
            timeout=90,
        )
        resp.raise_for_status()
        result = _extract_json(resp.json()["choices"][0]["message"]["content"])
        result.setdefault("dimension", dimension)
        result.setdefault("dimension_label", default["dimension_label"])
        for k in ("current_strategy", "case_reference", "suggestions", "reminder"):
            result.setdefault(k, default[k])
        return result
    except Exception as e:
        print(f"[deepen_assistant] 深化失败: {e}")
        return default


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="ArchAI 深化助手测试")
    parser.add_argument("--task", default="", help="设计任务")
    parser.add_argument("--dim", default="material", help="light/material/sequence/behavior")
    args = parser.parse_args()

    direction = {"name": "光之甬道·静谧沉思型", "core_strategy": "用连续光线+路径控制制造仪式感", "cases": ["光之教堂"]}
    result = deepen(args.task or "设计一个100㎡校园纪念空间", direction, args.dim)
    print(json.dumps(result, ensure_ascii=False, indent=2))
