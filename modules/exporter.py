"""
ArchAI Knowledge Base Generator — exporter.py
Stage 3: JSON + Dify-optimized Markdown 输出

Converts facts + analysis into final knowledge base files
suitable for Dify import.
"""

import json
import re
from datetime import datetime
from pathlib import Path


def vision_to_markdown_section(vision_result: dict, image_dir: str = "") -> str:
    """
    Convert Qwen-VL vision analysis results to a Dify-optimized Markdown section.

    Note: Qwen-VL output already contains structured headings (### 平面组织分析 etc),
    so we embed the raw analysis text directly to avoid duplicate headings.

    Args:
        vision_result: Output from vision_analyzer.run_vision_pipeline()
        image_dir: Relative path to images (for embedding image references)

    Returns:
        Markdown section string (empty if no vision data)
    """
    if not vision_result or not any([
        vision_result.get("plan_analysis"),
        vision_result.get("section_analysis"),
        vision_result.get("photo_analyses"),
    ]):
        return ""

    lines = ["## 视觉分析", ""]

    # Plan analysis
    if vision_result.get("plan_analysis"):
        if image_dir:
            lines.append(f"![平面图]({image_dir}/plan.jpg)")
            lines.append("")
        lines.append(vision_result["plan_analysis"])
        lines.append("")

    # Section analysis
    if vision_result.get("section_analysis"):
        if image_dir:
            lines.append(f"![剖面图]({image_dir}/section.jpg)")
            lines.append("")
        lines.append(vision_result["section_analysis"])
        lines.append("")

    # Photo analyses
    for i, pa in enumerate(vision_result.get("photo_analyses", []), 1):
        img_name = pa.get("image", f"space_{i}.jpg")
        if image_dir:
            lines.append(f"![空间照片{i}]({image_dir}/{img_name})")
            lines.append("")
        lines.append(pa.get("analysis", ""))
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def facts_to_markdown(
    facts: dict,
    analysis: dict,
    sources: list[dict] | None = None,
    vision: dict | None = None,
    image_dir: str = "",
) -> str:
    """
    Generate Dify-optimized Markdown from facts and analysis (LOCAL version).
    This is a template-driven local generator — no LLM API call needed.
    Use when you want deterministic, fast output.

    Args:
        facts: Output from analyzer.extract_facts()
        analysis: Output from analyzer.analyze_for_teaching()
        sources: Optional list of {url, title} dicts
        vision: Optional output from vision_analyzer.run_vision_pipeline()
        image_dir: Relative path to images for embedding in Markdown

    Returns:
        Markdown string
    """
    bi = facts.get("basic_info", {})
    name = bi.get("name_cn", "未知建筑")

    lines = [f"# {name}", ""]

    # ── 基本信息 ──
    lines.append("## 基本信息")
    lines.append("")
    info_fields = [
        ("建筑师", bi.get("architect", "")),
        ("建成时间", str(bi.get("year", ""))),
        ("地点", bi.get("location", "")),
        ("类型", bi.get("type", "")),
        ("规模", bi.get("area", "")),
    ]
    for label, value in info_fields:
        if value and value not in ("资料不足", "None", ""):
            lines.append(f"- **{label}：** {value}")

    materials = facts.get("materials", [])
    if materials:
        lines.append(f"- **主要材料：** {', '.join(materials)}")

    lines.append("")

    # ── 设计理念 ──
    dc = analysis.get("design_concept", {})
    lines.append("## 设计理念")
    lines.append("")
    kw = dc.get("keywords", [])
    if kw:
        lines.append(f"**关键词：** {', '.join(kw)}")
        lines.append("")
    summary = dc.get("summary", "") or dc.get("analysis", "")
    if summary:
        lines.append(summary)
        lines.append("")

    # ── 空间组织 ──
    sa = analysis.get("spatial_analysis", {})
    lines.append("## 空间组织")
    lines.append("")
    sa_kw = sa.get("keywords", [])
    if sa_kw:
        lines.append(f"**关键词：** {', '.join(sa_kw)}")
        lines.append("")

    for field in ["layout", "circulation", "experience"]:
        content = sa.get(field, "")
        if content and content not in ("资料不足，无法判断", ""):
            lines.append(content)
            lines.append("")

    # ── 材料与构造 ──
    ma = analysis.get("material_analysis", {})
    lines.append("## 材料与构造")
    lines.append("")
    ma_kw = ma.get("keywords", [])
    if ma_kw:
        lines.append(f"**关键词：** {', '.join(ma_kw)}")
        lines.append("")

    for field in ["material_logic", "material_space_relationship"]:
        content = ma.get(field, "")
        if content and content not in ("资料不足，无法判断", ""):
            lines.append(content)
            lines.append("")

    # ── 光环境 ──
    la = analysis.get("light_analysis", {})
    if la:
        lines.append("## 光环境")
        lines.append("")
        la_kw = la.get("keywords", [])
        if la_kw:
            lines.append(f"**关键词：** {', '.join(la_kw)}")
            lines.append("")

        for field in ["strategy", "effect"]:
            content = la.get(field, "")
            if content and content not in ("资料不足，无法判断", ""):
                lines.append(content)
                lines.append("")

    # ── 可迁移设计策略 ──
    tv = analysis.get("teaching_value", {})
    strategies = tv.get("design_strategies", [])
    if strategies:
        lines.append("## 可迁移设计策略")
        lines.append("")

        # Collect scenarios
        scenarios = set()
        for s in strategies:
            sc = s.get("application_scenario", "")
            if sc:
                scenarios.add(sc)
        if scenarios:
            lines.append(f"**适用场景：** {', '.join(scenarios)}")
            lines.append("")

        for i, s in enumerate(strategies, 1):
            strategy = s.get("strategy", "")
            if strategy:
                lines.append(f"{i}. **{strategy}**")
                scenario = s.get("application_scenario", "")
                if scenario:
                    lines.append(f"   - 适用：{scenario}")
                lines.append("")

    # ── 对学生设计的启发 ──
    points = tv.get("learning_points", [])
    if points:
        lines.append("## 对学生设计的启发")
        lines.append("")
        for i, p in enumerate(points, 1):
            point = p.get("point", "")
            why = p.get("why_important", "")
            if point:
                lines.append(f"{i}. **{point}**")
                if why:
                    lines.append(f"   - {why}")
                lines.append("")

    # ── 视觉分析（Phase 3：图片理解）──
    if vision:
        vision_md = vision_to_markdown_section(vision, image_dir)
        if vision_md:
            lines.append(vision_md)

    # ── 来源 ──
    if sources:
        lines.append("## 来源")
        lines.append("")
        for s in sources:
            url = s.get("url", "")
            title = s.get("title", url)
            if url:
                lines.append(f"- [{title}]({url})")
        lines.append("")

    return "\n".join(lines)


def save_output(
    building_name: str,
    markdown: str,
    facts: dict,
    analysis: dict,
    sources: list[dict] | None = None,
    vision: dict | None = None,
    output_dir: str | Path = "",
) -> dict:
    """
    Save Markdown and JSON output files.

    Args:
        building_name: Building name for file naming
        markdown: Markdown content string
        facts: Facts dict
        analysis: Analysis dict
        sources: Source URLs
        vision: Optional vision analysis result
        output_dir: Base output directory

    Returns:
        dict with output file paths
    """
    base = Path(output_dir) if output_dir else Path(__file__).resolve().parent.parent
    md_dir = base / "output" / "markdown"
    json_dir = base / "output" / "json"
    md_dir.mkdir(parents=True, exist_ok=True)
    json_dir.mkdir(parents=True, exist_ok=True)

    safe_name = re.sub(r"[^\w\-_一-鿿]", "_", building_name)

    # Save Markdown
    md_path = md_dir / f"{safe_name}_案例分析.md"
    md_path.write_text(markdown, encoding="utf-8")

    # Save JSON
    json_path = json_dir / f"{safe_name}_案例分析.json"
    output_data = {
        "generated_at": datetime.now().isoformat(),
        "building_name": building_name,
        "facts": facts,
        "analysis": analysis,
        "markdown": markdown,
        "sources": sources or [],
        "vision": vision,
    }
    json_path.write_text(json.dumps(output_data, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "markdown": str(md_path),
        "json": str(json_path),
    }


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("用法: python exporter.py <facts.json> <analysis.json> [建筑名称]")
        print("  或:  python exporter.py <full_output.json>")
        sys.exit(1)

    # Load inputs
    if len(sys.argv) >= 3:
        facts = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
        analysis = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
        name = sys.argv[3] if len(sys.argv) > 3 else facts.get("basic_info", {}).get("name_cn", "unknown")
    else:
        full = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
        facts = full.get("facts", {})
        analysis = full.get("analysis", {})
        name = full.get("building_name", "unknown")

    md = facts_to_markdown(facts, analysis)
    paths = save_output(name, md, facts, analysis)
    print(f"✅ Markdown: {paths['markdown']}")
    print(f"✅ JSON:     {paths['json']}")
