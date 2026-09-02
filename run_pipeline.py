"""End-to-end pipeline test: Architect -> Crawl -> Analyze -> Export"""
import json, re, sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

from modules.architect import search_by_name
from modules.crawler import search_ddg, fetch_page, rank_sources
from modules.analyzer import extract_facts, analyze_for_teaching, generate_markdown

# ── Config ──
ARCHITECT = "Tadao Ando"
MAX_WORKS = 3

# ── Step 1: Architect ──
print(f"[Step 1] Architect: {ARCHITECT}")
arch_data = search_by_name(ARCHITECT, max_projects=MAX_WORKS)
arch = arch_data["architect"]
works = arch_data["projects"]
print(f"  Source: {arch_data['source']}")
print(f"  Works: {len(works)}")

# ── Step 2-5: Per work ──
for wi, work in enumerate(works):
    name_en = work["name"]
    name_cn = work["name_cn"] or name_en
    print(f"\n{'='*50}")
    print(f"[{wi+1}/{len(works)}] {name_cn} ({name_en})")
    print("=" * 50)

    # Crawl
    print("  [Crawl] Searching...")
    queries = [
        f"{name_en} {ARCHITECT} architecture",
        f"{name_en} design analysis",
    ]
    all_results = []
    seen = set()
    for q in queries:
        try:
            for r in search_ddg(q, max_results=6):
                if r["url"] not in seen:
                    seen.add(r["url"])
                    all_results.append(r)
        except Exception as e:
            print(f"    Search error: {e}")

    if not all_results:
        print("    No results, skipping")
        continue

    ranked = rank_sources([r["url"] for r in all_results])[:3]
    print(f"    Found {len(all_results)} results, top 3 to fetch")

    sources = []
    for url in ranked:
        try:
            text = fetch_page(url)
            if text and len(text) > 500:
                sources.append({"url": url, "title": url, "text": text})
                print(f"    OK: {url[:80]} ({len(text)} chars)")
            else:
                print(f"    SKIP: too short ({len(text)} chars)")
        except Exception as e:
            print(f"    FAIL: {url[:60]} - {e}")

    if not sources:
        print("    No usable sources, skipping")
        continue

    combined = "\n\n---\n\n".join(
        f"Source: {s['url']}\n{s['text']}" for s in sources
    )

    # Analyze
    print("  [Analyze] Stage 1: extract_facts...")
    facts = extract_facts(combined, name_cn)
    print(f"    completeness: {facts.get('completeness', {})}")

    print("  [Analyze] Stage 2: analyze_for_teaching...")
    analysis = analyze_for_teaching(facts)
    tv = analysis.get("teaching_value", {})
    print(f"    strategies: {len(tv.get('design_strategies', []))}")
    print(f"    learning_points: {len(tv.get('learning_points', []))}")

    print("  [Analyze] Stage 3: generate_markdown...")
    md = generate_markdown(facts, analysis)
    md = md.strip()
    if md.startswith("```"):
        md = re.sub(r"^```\w*\n?", "", md)
    if md.endswith("```"):
        md = md[:-3].strip()

    # Add real sources
    md += "\n\n## 来源\n"
    for s in sources:
        md += f"- [{s['url']}]({s['url']})\n"

    # Save
    safe_name = re.sub(r"[^\w\-_]", "_", name_cn or name_en)
    md_path = Path(f"output/markdown/{safe_name}_案例分析.md")
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(md, encoding="utf-8")

    json_path = Path(f"output/json/{safe_name}_案例分析.json")
    json_path.parent.mkdir(parents=True, exist_ok=True)
    full = {
        "building_name": name_cn or name_en,
        "architect": ARCHITECT,
        "facts": facts,
        "analysis": analysis,
        "markdown": md,
        "sources": [{"url": s["url"]} for s in sources],
    }
    json_path.write_text(json.dumps(full, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"  [DONE] {md_path}")
    print(f"  [DONE] {json_path}")

print(f"\n{'='*50}")
print(f"Pipeline complete! Check output/markdown/ and output/json/")
