"""End-to-end batch pipeline: 5 Architects x 5 Cases = 25 Markdown files"""
import json, re, sys, os, time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

from modules.architect import search_by_name
from modules.crawler import search_ddg, fetch_page, rank_sources
from modules.analyzer import extract_facts, analyze_for_teaching, generate_markdown

# ── Config ──
ARCHITECTS = [
    "Tadao Ando",
    "Le Corbusier",
    "Louis Kahn",
    "Mies van der Rohe",
    "Peter Zumthor",
]
MAX_WORKS_PER = 5
FAIL_FAST = False  # Set True to stop on first error

# ── Stats ──
stats = {"architects_done": 0, "cases_done": 0, "cases_failed": 0, "total_api_calls": 0}

for arch_name in ARCHITECTS:
    print(f"\n{'#'*60}")
    print(f"# ARCHITECT: {arch_name}")
    print(f"{'#'*60}")

    # Step 1: Architect
    try:
        arch_data = search_by_name(arch_name, max_projects=MAX_WORKS_PER)
    except Exception as e:
        print(f"  [ERROR] architect search failed: {e}")
        if FAIL_FAST: raise
        continue

    arch = arch_data["architect"]
    works = arch_data["projects"]
    print(f"  Source: {arch_data['source']} | Country: {arch.get('country','')} | Works: {len(works)}")

    for wi, work in enumerate(works):
        name_en = work["name"]
        name_cn = work["name_cn"] or name_en
        print(f"\n  [{wi+1}/{len(works)}] {name_cn} ({name_en})")

        try:
            # Crawl
            print(f"    [Crawl] Searching...")
            queries = [
                f"{name_en} {arch_name} architecture",
                f"{name_en} design analysis",
            ]
            all_results = []
            seen = set()
            for q in queries:
                try:
                    for r in search_ddg(q, max_results=6):
                        if r["url"] not in seen:
                            seen.add(r["url"]); all_results.append(r)
                except Exception as e:
                    print(f"      Search error: {e}")

            if not all_results:
                print(f"    [SKIP] No search results")
                stats["cases_failed"] += 1
                continue

            ranked = rank_sources([r["url"] for r in all_results])[:3]
            sources = []
            for url in ranked:
                try:
                    text = fetch_page(url)
                    if text and len(text) > 500:
                        sources.append({"url": url, "title": url, "text": text})
                        print(f"      OK: {url[:70]} ({len(text)} chars)")
                    else:
                        print(f"      SHORT: {url[:50]} ({len(text)} chars)")
                except Exception as e:
                    print(f"      FAIL: {url[:50]} - {e}")

            if not sources:
                print(f"    [SKIP] No usable sources")
                stats["cases_failed"] += 1
                continue

            combined = "\n\n---\n\n".join(f"Source: {s['url']}\n{s['text']}" for s in sources)

            # Analyze
            print(f"    [Analyze] S1 extract...")
            facts = extract_facts(combined, name_cn)
            stats["total_api_calls"] += 1

            print(f"    [Analyze] S2 analyze...")
            analysis = analyze_for_teaching(facts)
            stats["total_api_calls"] += 1
            tv = analysis.get("teaching_value", {})
            print(f"      strategies={len(tv.get('design_strategies',[]))} points={len(tv.get('learning_points',[]))}")

            print(f"    [Analyze] S3 generate markdown...")
            md = generate_markdown(facts, analysis)
            stats["total_api_calls"] += 1
            md = md.strip()
            if md.startswith("```"):
                md = re.sub(r"^```\w*\n?", "", md)
            if md.endswith("```"):
                md = md[:-3].strip()

            md += "\n\n## 来源\n"
            for s in sources:
                md += f"- [{s['url']}]({s['url']})\n"

            # Save under architect subdirectory
            safe_arch = re.sub(r"[^\w\-_]", "_", arch_name)
            safe_name = re.sub(r"[^\w\-_一-鿿]", "_", name_cn or name_en)
            md_dir = Path(f"output/markdown/{safe_arch}")
            md_dir.mkdir(parents=True, exist_ok=True)
            md_path = md_dir / f"{safe_name}_案例分析.md"
            md_path.write_text(md, encoding="utf-8")

            json_dir = Path(f"output/json/{safe_arch}")
            json_dir.mkdir(parents=True, exist_ok=True)
            json_path = json_dir / f"{safe_name}_案例分析.json"
            full = {
                "building_name": name_cn or name_en,
                "architect": arch_name,
                "facts": facts,
                "analysis": analysis,
                "markdown": md,
                "sources": [{"url": s["url"]} for s in sources],
            }
            json_path.write_text(json.dumps(full, ensure_ascii=False, indent=2), encoding="utf-8")

            print(f"    [DONE] md={md_path.name}")
            stats["cases_done"] += 1

            # Rate limit between works
            time.sleep(1)

        except Exception as e:
            print(f"    [FAIL] {e}")
            stats["cases_failed"] += 1
            if FAIL_FAST: raise
            continue

    stats["architects_done"] += 1
    print(f"\n  --- {arch_name} complete ---")

# ── Summary ──
print(f"\n{'='*60}")
print(f"BATCH COMPLETE")
print(f"{'='*60}")
print(f"  Architects: {stats['architects_done']}/{len(ARCHITECTS)}")
print(f"  Cases generated: {stats['cases_done']}")
print(f"  Cases failed: {stats['cases_failed']}")
print(f"  API calls: {stats['total_api_calls']}")

# List output tree
print(f"\nOutput tree:")
for arch_name in ARCHITECTS:
    safe_arch = re.sub(r"[^\w\-_]", "_", arch_name)
    md_dir = Path(f"output/markdown/{safe_arch}")
    if md_dir.exists():
        files = sorted(md_dir.glob("*.md"))
        print(f"  {arch_name}/ ({len(files)} cases)")
        for f in files:
            size = f.stat().st_size
            print(f"    {f.name} ({size:,} bytes)")
