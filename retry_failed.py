"""Retry failed cases from batch run — only generates missing Markdown files"""
import json, re, sys, os, time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

from modules.architect import search_by_name
from modules.crawler import search_ddg, fetch_page, rank_sources
from modules.analyzer import extract_facts, analyze_for_teaching, generate_markdown

# Only retry these architect-work combinations
RETRY_LIST = [
    # Tadao Ando — 4 missing
    ("Tadao Ando", "水之教堂", "Church on the Water"),
    ("Tadao Ando", "住吉的长屋", "Row House in Sumiyoshi"),
    ("Tadao Ando", "地中美术馆", "Chichu Art Museum"),
    ("Tadao Ando", "六甲集合住宅", "Rokko Housing"),
    # Le Corbusier — 5 missing
    ("Le Corbusier", "萨伏伊别墅", "Villa Savoye"),
    ("Le Corbusier", "马赛公寓", "Unite d'Habitation"),
    ("Le Corbusier", "朗香教堂", "Notre Dame du Haut"),
    ("Le Corbusier", "拉图雷特修道院", "La Tourette"),
    ("Le Corbusier", "卡朋特视觉艺术中心", "Carpenter Center"),
]

done = 0
failed = 0

for arch_name, name_cn, name_en in RETRY_LIST:
    safe_name = re.sub(r"[^\w\-_一-鿿]", "_", name_cn)
    safe_arch = re.sub(r"[^\w\-_]", "_", arch_name)
    md_path = Path(f"output/markdown/{safe_arch}/{safe_name}_案例分析.md")

    # Skip if already exists
    if md_path.exists():
        print(f"[SKIP] Already exists: {md_path.name}")
        continue

    print(f"\n[RETRY] {arch_name} — {name_cn} ({name_en})")

    try:
        # Crawl
        print(f"  [Crawl] Searching...")
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
                print(f"    Search error: {e}")

        ranked = rank_sources([r["url"] for r in all_results])[:3]
        sources = []
        for url in ranked:
            try:
                text = fetch_page(url)
                if text and len(text) > 500:
                    sources.append({"url": url, "title": url, "text": text})
                    print(f"    OK: {url[:70]} ({len(text)} chars)")
            except Exception as e:
                print(f"    FAIL: {url[:50]} - {e}")

        if not sources:
            print(f"  [SKIP] No sources"); failed += 1; continue

        combined = "\n\n---\n\n".join(f"Source: {s['url']}\n{s['text']}" for s in sources)

        # Analyze with retry
        for attempt in range(3):
            try:
                print(f"  [Analyze] S1 extract (attempt {attempt+1})...")
                facts = extract_facts(combined, name_cn)
                print(f"  [Analyze] S2 analyze...")
                analysis = analyze_for_teaching(facts)
                print(f"  [Analyze] S3 generate...")
                md = generate_markdown(facts, analysis)
                break
            except Exception as e:
                print(f"    API error: {e}")
                if attempt < 2:
                    print(f"    Retrying in 5s...")
                    time.sleep(5)
                else:
                    raise

        md = md.strip()
        if md.startswith("```"):
            md = re.sub(r"^```\w*\n?", "", md)
        if md.endswith("```"):
            md = md[:-3].strip()

        md += "\n\n## 来源\n"
        for s in sources:
            md += f"- [{s['url']}]({s['url']})\n"

        md_path.parent.mkdir(parents=True, exist_ok=True)
        md_path.write_text(md, encoding="utf-8")

        # Also save JSON
        json_dir = Path(f"output/json/{safe_arch}")
        json_dir.mkdir(parents=True, exist_ok=True)
        json_path = json_dir / f"{safe_name}_案例分析.json"
        json_path.write_text(json.dumps({
            "building_name": name_cn,
            "architect": arch_name,
            "facts": facts,
            "analysis": analysis,
            "markdown": md,
            "sources": [{"url": s["url"]} for s in sources],
        }, ensure_ascii=False, indent=2), encoding="utf-8")

        print(f"  [DONE] {md_path.name}")
        done += 1
        time.sleep(2)

    except Exception as e:
        print(f"  [FAIL] {e}")
        failed += 1
        continue

print(f"\nRetry done: {done} new, {failed} failed")
