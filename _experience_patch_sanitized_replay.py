"""Sanitized replay for residual professional-experience assertions.

Only the experiment prompt, confirmed user facts, and recalled sentences are
sent to DeepSeek. Production prompts, State, RAG, history, and source code are
not included.
"""

from __future__ import annotations

import json
from pathlib import Path
import re

import requests

import architect_chat as ac


OUT = Path(
    "../03_AI测试记录/项目日志/"
    "2026年8月24日_专业经验断言脱敏回放验证报告.md"
)

CASES = [
    {
        "title": "场地经验：南侧开敞到入口",
        "facts": ["基地南侧边界开敞", "基地北侧临现有建筑"],
        "sentences": [
            "- **南侧边界开敞** → 可承接主要到达与公共活动，适合放入口和公共性强的功能。",
            "- **北侧临现有建筑** → 是既有界面，适合放需要安静的后勤功能。",
        ],
        "strong_patterns": [
            r"南侧边界开敞.{0,35}(?:适合|可承接).{0,20}(?:入口|展览|公共)",
            r"北侧临现有建筑.{0,35}适合.{0,20}(?:安静|后勤)",
        ],
        "labor_terms": ["南侧", "入口", "北侧", "后勤"],
    },
    {
        "title": "类型经验：幼儿园空间关系",
        "facts": ["项目为6班幼儿园", "用户目标是方便老师照看"],
        "sentences": [
            "1. **活动室是枢纽**。",
            "2. **寝室与室外场地不直接相连**。",
        ],
        "strong_patterns": [
            r"活动室是枢纽",
            r"寝室与室外场地不直接相连",
        ],
        "labor_terms": ["活动室", "寝室", "室外场地"],
    },
]


def _request_payload(case: dict) -> tuple[str, list[str]]:
    candidates = case["sentences"]
    candidate_items = [
        {"id": f"C{index}", "text": sentence}
        for index, sentence in enumerate(candidates, start=1)
    ]
    prompt = (
        ac._EXPERIENCE_PATCH_INSTRUCTION
        + "\n\n【用户明确提供的事实】\n"
        + json.dumps(case["facts"], ensure_ascii=False)
        + "\n\n【必须逐条评审的召回候选句】\n"
        + json.dumps(candidate_items, ensure_ascii=False)
        + "\n\n这是一项脱敏离线回放。不得补充其他项目背景，只按以上事实判断。"
    )
    return prompt, candidates


def _strong_hits(text: str, patterns: list[str]) -> list[str]:
    """Count only unconditioned matches, not already downgraded candidate language."""
    hits = []
    for pattern in patterns:
        for line in (text or "").splitlines():
            if re.search(pattern, line) and not ac._EXPERIENCE_PATCH_CONDITIONAL_RE.search(line):
                hits.append(pattern)
                break
    return hits


def _run_case(case: dict) -> dict:
    prompt, candidates = _request_payload(case)
    raw_attempts = []
    parsed = None
    patch_payload = None
    for attempt in range(2):
        response = requests.post(
            ac.DEEPSEEK_URL,
            headers={
                "Authorization": f"Bearer {ac.DEEPSEEK_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "deepseek-chat",
                "messages": [
                    {"role": "system", "content": prompt},
                    {
                        "role": "user",
                        "content": (
                            "只输出 JSON 局部补丁。"
                            if attempt == 0
                            else "上次输出不完整。请重新输出完整 JSON 对象。"
                        ),
                    },
                ],
                "temperature": 0.0,
                "max_tokens": 1400,
            },
            timeout=120,
        )
        response.raise_for_status()
        raw_response = response.json()["choices"][0]["message"]["content"]
        raw_attempts.append(raw_response)
        parsed = ac._parse_experience_patch_payload(raw_response)
        patch_payload = ac._experience_reviews_to_patch_payload(parsed, candidates)
        if patch_payload is not None:
            break
    original = "\n".join(candidates)
    revised = ac._apply_experience_patches(original, patch_payload)
    reviews = parsed.get("reviews") if isinstance(parsed, dict) else None
    strong_before = _strong_hits(original, case["strong_patterns"])
    strong_after = _strong_hits(revised, case["strong_patterns"])
    missing_labor = [term for term in case["labor_terms"] if term not in revised]
    degradation = [
        term for term in ("无法判断", "信息不足", "不能给出建议", "内部检查结果")
        if term in revised
    ]
    return {
        "title": case["title"],
        "facts": case["facts"],
        "original": original,
        "raw_response": "\n\n--- retry ---\n\n".join(raw_attempts),
        "reviews": reviews,
        "contract_valid": patch_payload is not None,
        "patch_count": len((patch_payload or {}).get("patches", [])),
        "revised": revised,
        "strong_before": strong_before,
        "strong_after": strong_after,
        "missing_labor": missing_labor,
        "degradation": degradation,
    }


def _write_report(results: list[dict]) -> None:
    before = sum(len(result["strong_before"]) for result in results)
    after = sum(len(result["strong_after"]) for result in results)
    contracts_valid = all(result["contract_valid"] for result in results)
    labor_kept = all(not result["missing_labor"] for result in results)
    no_degradation = all(not result["degradation"] for result in results)
    if contracts_valid and after < before and labor_kept and no_degradation:
        conclusion = "支持：脱敏回放中强经验断言下降，设计信息保持，未出现免责声明退化。"
    elif contracts_valid and after < before:
        conclusion = "部分支持：强经验断言下降，但仍有设计信息丢失或退化。"
    else:
        conclusion = "不支持：检查契约无效，或强经验断言没有下降。"

    lines = [
        "# 专业经验断言脱敏回放验证报告",
        "",
        "## 实验边界",
        "",
        "仅向 DeepSeek 发送实验检查提示、用户明确事实和被召回句子。未发送完整 SYSTEM_PROMPT、State、RAG、历史对话或项目源码。",
        "",
        "## 汇总",
        "",
        f"- 强经验断言：{before} → {after}",
        f"- 检查契约有效：{'是' if contracts_valid else '否'}",
        f"- 设计信息保持：{'是' if labor_kept else '否'}",
        f"- 免责声明退化：{'无' if no_degradation else '有'}",
        f"- 结论：{conclusion}",
        "",
    ]
    for result in results:
        lines.extend([
            f"## {result['title']}",
            "",
            f"用户明确事实：{'；'.join(result['facts'])}",
            "",
            f"强经验断言：{len(result['strong_before'])} → {len(result['strong_after'])}",
            "",
            f"检查契约有效：{'是' if result['contract_valid'] else '否'}；补丁数量：{result['patch_count']}",
            "",
            f"设计信息缺失：{('、'.join(result['missing_labor']) if result['missing_labor'] else '无')}",
            "",
            f"退化：{('、'.join(result['degradation']) if result['degradation'] else '无')}",
            "",
            "### 原句",
            "",
            result["original"],
            "",
            "### Shadow 判断",
            "",
            "```json",
            json.dumps(result["reviews"], ensure_ascii=False, indent=2),
            "```",
            "",
            "### 模型原始返回",
            "",
            "```text",
            result["raw_response"],
            "```",
            "",
            "### 局部补丁后",
            "",
            result["revised"],
            "",
        ])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    if not ac.DEEPSEEK_API_KEY:
        raise RuntimeError("DEEPSEEK_API_KEY is not configured")
    results = [_run_case(case) for case in CASES]
    _write_report(results)
    print(f"report={OUT.resolve()}")
    print(
        "assertions "
        f"before={sum(len(result['strong_before']) for result in results)} "
        f"after={sum(len(result['strong_after']) for result in results)}"
    )
    print(f"patches={sum(result['patch_count'] for result in results)}")
    print(f"labor_kept={all(not result['missing_labor'] for result in results)}")
    print(f"degradation={sum(bool(result['degradation']) for result in results)}/{len(results)}")


if __name__ == "__main__":
    main()
