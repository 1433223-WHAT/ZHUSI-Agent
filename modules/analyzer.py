"""
ArchAI Knowledge Base Generator — analyzer.py
Core AI pipeline: extract_facts → analyze_for_teaching → generate_markdown

Stage 1: Raw text → Structured facts (JSON)
Stage 2: Facts → Architectural teaching analysis (JSON)
Stage 3: Facts + Analysis → Dify-optimized Markdown
"""

import json
import os
import re
from pathlib import Path
from datetime import datetime

import requests

# ── DeepSeek API config ──────────────────────────────────────────────
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1/chat/completions"
DEEPSEEK_MODEL = "deepseek-chat"

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


def _call_deepseek(system_prompt: str, user_message: str, temperature: float = 0.3) -> str:
    """Call DeepSeek API and return response text."""
    if not DEEPSEEK_API_KEY:
        raise RuntimeError("DEEPSEEK_API_KEY 未设置。请在环境变量中设置或直接在 config 中填写。")

    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        "temperature": temperature,
        "max_tokens": 4096,
    }

    resp = requests.post(DEEPSEEK_BASE_URL, headers=headers, json=payload, timeout=120)
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"]


def _extract_json(text: str) -> dict:
    """Extract JSON object from LLM response (handles markdown code blocks)."""
    # Try parsing directly first
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try ```json ... ``` code block
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # Try to find { ... } boundaries
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            pass

    raise ValueError(f"无法从 LLM 响应中解析 JSON。原始响应:\n{text[:500]}")


def _load_prompt(name: str) -> str:
    """Load a prompt template from prompts/ directory."""
    path = PROMPTS_DIR / name
    if not path.exists():
        raise FileNotFoundError(f"Prompt 文件不存在: {path}")
    return path.read_text(encoding="utf-8")


# ── Stage 1: 事实提取 ─────────────────────────────────────────────────

def extract_facts(text: str, building_name: str = "") -> dict:
    """
    Stage 1: Extract structured facts from raw architectural text.

    Args:
        text: Raw web page / document text about a building
        building_name: Optional building name for context

    Returns:
        dict with basic_info, materials, structure, spatial_features,
             light_strategy, facts, completeness
    """
    prompt_template = _load_prompt("extract.txt")
    system_prompt = (
        "你是一名建筑资料整理专家。你的任务是从给定的建筑文本中提取结构化事实。"
        "只提取原文明确出现的信息，绝不编造。回复必须是合法的 JSON。"
    )
    user_message = prompt_template.replace("{text}", text)

    raw_response = _call_deepseek(system_prompt, user_message, temperature=0.1)
    facts = _extract_json(raw_response)

    # Inject building name if provided and not in extracted facts
    if building_name and facts.get("basic_info", {}).get("name_cn", "") in ("", "资料不足"):
        facts.setdefault("basic_info", {})["name_cn"] = building_name

    return facts


# ── Stage 2: 建筑学教学分析 ─────────────────────────────────────────────

def analyze_for_teaching(facts: dict) -> dict:
    """
    Stage 2: Generate architectural teaching analysis from structured facts.

    Strict anti-hallucination: every analysis point must reference a Stage 1 fact.
    "资料不足" is preferred over speculation.

    Args:
        facts: Output from extract_facts()

    Returns:
        dict with design_concept, spatial_analysis, material_analysis,
             light_analysis, teaching_value, data_gaps
    """
    prompt_template = _load_prompt("analyze.txt")
    system_prompt = (
        "你是一名建筑教育专家。你的任务是基于已提取的建筑事实，"
        "进行面向建筑学教学的专业分析。所有分析必须基于提供的事实，"
        "绝不编造。回复必须是合法的 JSON。"
    )
    user_message = prompt_template.replace("{facts_json}", json.dumps(facts, ensure_ascii=False, indent=2))

    raw_response = _call_deepseek(system_prompt, user_message, temperature=0.3)
    analysis = _extract_json(raw_response)
    return analysis


# ── Stage 3: Markdown 生成 ─────────────────────────────────────────────

def generate_markdown(facts: dict, analysis: dict) -> str:
    """
    Stage 3: Generate Dify-optimized Markdown from facts and analysis.

    Args:
        facts: Output from extract_facts()
        analysis: Output from analyze_for_teaching()

    Returns:
        Dify-optimized Markdown string
    """
    prompt_template = _load_prompt("generate.txt")
    system_prompt = (
        "你是一名建筑知识库编辑。你的任务是将建筑事实和分析整合为"
        "面向 Dify 知识库优化的 Markdown 文件。回复必须是纯 Markdown，"
        "不要包裹在代码块中。"
    )
    user_message = prompt_template.replace(
        "{facts_json}", json.dumps(facts, ensure_ascii=False, indent=2)
    ).replace(
        "{analysis_json}", json.dumps(analysis, ensure_ascii=False, indent=2)
    )

    raw_response = _call_deepseek(system_prompt, user_message, temperature=0.4)

    # Strip code block wrappers if present
    md = raw_response.strip()
    if md.startswith("```markdown"):
        md = md[len("```markdown"):].strip()
    elif md.startswith("```"):
        md = md[3:].strip()
    if md.endswith("```"):
        md = md[:-3].strip()

    return md


# ── Pipeline ───────────────────────────────────────────────────────────

def run_pipeline(
    text: str,
    building_name: str = "",
    output_dir: str | Path = "",
    save_intermediates: bool = True,
) -> dict:
    """
    Run the full analysis pipeline: extract → analyze → generate.

    Args:
        text: Raw architectural text (from web or document)
        building_name: Building name for file naming and context
        output_dir: Where to save output files (default: output/)
        save_intermediates: Save facts.json and analysis.json to data/json/

    Returns:
        dict with keys: building_name, facts, analysis, markdown, output_paths
    """
    base = Path(output_dir) if output_dir else Path(__file__).resolve().parent.parent
    markdown_dir = base / "output" / "markdown"
    json_dir = base / "data" / "json"
    markdown_dir.mkdir(parents=True, exist_ok=True)
    json_dir.mkdir(parents=True, exist_ok=True)

    # Stage 1
    print(f"[Stage 1] 提取事实: {building_name or '(未指定)'}")
    facts = extract_facts(text, building_name)

    # Use extracted name if not provided
    name = building_name or facts.get("basic_info", {}).get("name_cn", "unknown")
    safe_name = name.replace("/", "_").replace("\\", "_").replace(" ", "_")

    if save_intermediates:
        facts_path = json_dir / f"{safe_name}_facts.json"
        facts_path.write_text(json.dumps(facts, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  → 已保存: {facts_path}")

    # Stage 2
    print(f"[Stage 2] 教学分析: {name}")
    analysis = analyze_for_teaching(facts)

    if save_intermediates:
        analysis_path = json_dir / f"{safe_name}_analysis.json"
        analysis_path.write_text(json.dumps(analysis, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  → 已保存: {analysis_path}")

    # Stage 3
    print(f"[Stage 3] 生成 Markdown: {name}")
    markdown = generate_markdown(facts, analysis)

    md_path = markdown_dir / f"{safe_name}_案例分析.md"
    md_path.write_text(markdown, encoding="utf-8")
    print(f"  → 已保存: {md_path}")

    # Also save full JSON
    json_output_path = base / "output" / "json" / f"{safe_name}_案例分析.json"
    json_output_path.parent.mkdir(parents=True, exist_ok=True)
    full_output = {
        "generated_at": datetime.now().isoformat(),
        "building_name": name,
        "facts": facts,
        "analysis": analysis,
        "markdown": markdown,
    }
    json_output_path.write_text(json.dumps(full_output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  → 已保存: {json_output_path}")

    return {
        "building_name": name,
        "facts": facts,
        "analysis": analysis,
        "markdown": markdown,
        "output_paths": {
            "markdown": str(md_path),
            "json": str(json_output_path),
        },
    }


# ── CLI entry ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("用法: python analyzer.py <source_text.txt> [建筑名称]")
        print("示例: python analyzer.py data/raw/guang_zhijiaotang_source.txt 光之教堂")
        sys.exit(1)

    source_path = Path(sys.argv[1])
    if not source_path.exists():
        print(f"文件不存在: {source_path}")
        sys.exit(1)

    source_text = source_path.read_text(encoding="utf-8")
    bldg_name = sys.argv[2] if len(sys.argv) > 2 else ""

    if not DEEPSEEK_API_KEY:
        print("⚠ 警告: DEEPSEEK_API_KEY 未设置。请在环境变量中设置后再运行。")
        print("  export DEEPSEEK_API_KEY=sk-xxxx")
        sys.exit(1)

    result = run_pipeline(source_text, bldg_name)
    print(f"\n✅ 完成: {result['output_paths']['markdown']}")
