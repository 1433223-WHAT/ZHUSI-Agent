"""
ArchAI Knowledge Base Generator — architect.py
Wikidata API → 建筑师信息 + 代表作品列表 (含 QID)

Uses Wikidata SPARQL endpoint (free, no API key):
  https://query.wikidata.org/sparql

Example:
  Input:  "Tadao Ando"
  Output: {architect: {...}, projects: [{name, year, location, qid}, ...]}
"""

import json
import re
import sys
from pathlib import Path
from urllib.parse import quote

import requests

# Allow importing master_works from parent directory
_MASTER_WORKS_PATH = Path(__file__).resolve().parent.parent
if str(_MASTER_WORKS_PATH) not in sys.path:
    sys.path.insert(0, str(_MASTER_WORKS_PATH))

try:
    from master_works import MASTER_WORKS, get_works as _mw_get_works, get_architect_info as _mw_get_info
    _HAS_MASTER_WORKS = True
except ImportError:
    _HAS_MASTER_WORKS = False
    MASTER_WORKS = {}

WIKIDATA_SPARQL_URL = "https://query.wikidata.org/sparql"
HEADERS = {
    "User-Agent": "ArchAI-Knowledge-Builder/0.1 (educational project)",
    "Accept": "application/json",
}


def search_architect(name: str, lang: str = "zh") -> dict | None:
    """
    Search for an architect on Wikidata by name.

    Returns the best-matching Wikidata entity with basic info.
    """
    # Try exact match first, then fall back to contains
    query = f"""
    SELECT ?architect ?architectLabel ?birthDate ?country ?countryLabel WHERE {{
      ?architect wdt:P31 wd:Q5.
      ?architect wdt:P106 wd:Q42973.
      ?architect rdfs:label ?architectLabel.
      FILTER(CONTAINS(LCASE(?architectLabel), LCASE("{name}")))
      FILTER(LANG(?architectLabel) IN ("zh", "en", "ja"))
      OPTIONAL {{ ?architect wdt:P569 ?birthDate. }}
      OPTIONAL {{ ?architect wdt:P27 ?country. }}
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "{lang},en,ja". }}
    }}
    LIMIT 5
    """
    url = f"{WIKIDATA_SPARQL_URL}?format=json&query={quote(query)}"
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    bindings = data.get("results", {}).get("bindings", [])
    if not bindings:
        return None

    b = bindings[0]
    qid = b.get("architect", {}).get("value", "").rsplit("/", 1)[-1]

    return {
        "name": b.get("architectLabel", {}).get("value", name),
        "qid": qid,
        "birth": b.get("birthDate", {}).get("value", "")[:4] if "birthDate" in b else "",
        "country": b.get("countryLabel", {}).get("value", ""),
    }


def get_projects(architect_qid: str, max_projects: int = 5, lang: str = "zh") -> list[dict]:
    """
    Get notable architectural works for a given architect QID.

    Uses Wikidata properties:
      P84 (architect) or P631 (structural engineer related)
      P31 (instance of) → building/architectural structure types
      P571 (inception/construction date)
      P276 (location)
    """
    query = f"""
    SELECT DISTINCT ?project ?projectLabel ?year ?location ?locationLabel WHERE {{
      ?project wdt:P84 wd:{architect_qid}.
      OPTIONAL {{ ?project wdt:P571 ?inception. BIND(YEAR(?inception) AS ?year) }}
      OPTIONAL {{ ?project wdt:P276 ?location. }}
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "{lang},en,ja". }}
    }}
    ORDER BY DESC(?year)
    LIMIT {max_projects * 2}
    """
    url = f"{WIKIDATA_SPARQL_URL}?format=json&query={quote(query)}"
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    bindings = data.get("results", {}).get("bindings", [])
    if not bindings:
        return []

    seen_names = set()
    projects = []
    for b in bindings:
        name = b.get("projectLabel", {}).get("value", "")
        if not name:
            name = b.get("project", {}).get("value", "").rsplit("/", 1)[-1]
            name = name.replace("Q", "")

        # Deduplicate by name (case-insensitive)
        name_lower = name.lower()
        if name_lower in seen_names:
            continue
        seen_names.add(name_lower)

        projects.append({
            "name": name,
            "qid": b.get("project", {}).get("value", "").rsplit("/", 1)[-1],
            "year": b.get("year", {}).get("value", ""),
            "location": b.get("locationLabel", {}).get("value", ""),
        })

    # Return top N
    return projects[:max_projects]


def search_by_name(name: str, max_projects: int = 5, lang: str = "zh") -> dict:
    """
    Hybrid mode:
    1. Wikidata → 建筑师基本信息 (QID, birth, country)
    2. master_works.py → 经典作品列表 (教学价值排序)
    3. Fallback: 如果 master_works 无此建筑师, 用 Wikidata P84

    Args:
        name: Architect name (English preferred for lookup)
        max_projects: Maximum number of projects to return

    Returns:
        {
            "architect": {name, name_cn, qid, birth, country, style_keywords},
            "projects": [{name, name_cn, year, location, type, keywords, ...}, ...],
            "source": "master_works" | "wikidata" | "hybrid"
        }
    """
    # Step 1: Try master_works first
    mw_entry = _mw_get_works(name) if _HAS_MASTER_WORKS else None
    mw_info = _mw_get_info(name) if _HAS_MASTER_WORKS else None

    if mw_entry and mw_info:
        # Use curated works from master_works
        projects = []
        for w in mw_entry[:max_projects]:
            projects.append({
                "name": w["name"],
                "name_cn": w.get("name_cn", ""),
                "year": w.get("year", ""),
                "location": w.get("location", ""),
                "type": w.get("type", ""),
                "keywords": w.get("keywords", []),
                "design_topics": w.get("design_topics", []),
                "teaching_value": w.get("teaching_value", ""),
                "qid": "",  # Could be enriched from Wikidata later
            })

        return {
            "architect": {
                "name": name,
                "name_cn": "",
                "qid": mw_info["qid"],
                "birth": str(mw_info.get("birth", "")),
                "country": mw_info.get("country", ""),
                "style_keywords": mw_info.get("style_keywords", []),
            },
            "projects": projects,
            "source": "master_works",
        }

    # Step 2: Fallback to Wikidata for architect info
    arch = search_architect(name, lang)
    if not arch:
        raise RuntimeError(f"未找到建筑师: {name}。请确认名称正确或将其加入 master_works.py。")

    # Step 3: Try Wikidata projects as fallback
    projects = get_projects(arch["qid"], max_projects, lang)
    projects_out = []
    for p in projects:
        projects_out.append({
            "name": p["name"],
            "name_cn": "",
            "year": p["year"],
            "location": p.get("location", ""),
            "type": "",
            "keywords": [],
            "design_topics": [],
            "teaching_value": "",
            "qid": p["qid"],
        })

    return {
        "architect": {
            "name": arch["name"],
            "name_cn": "",
            "qid": arch["qid"],
            "birth": arch.get("birth", ""),
            "country": arch.get("country", ""),
            "style_keywords": [],
        },
        "projects": projects_out,
        "source": "wikidata",
    }


def save_architect_json(data: dict, output_dir: str | Path = "") -> Path:
    """Save architect data to JSON file."""
    base = Path(output_dir) if output_dir else Path(__file__).resolve().parent.parent
    json_dir = base / "data" / "json"
    json_dir.mkdir(parents=True, exist_ok=True)

    safe_name = re.sub(r"[^\w\-_一-鿿]", "_", data["architect"]["name"])
    path = json_dir / f"{safe_name}_architect.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


if __name__ == "__main__":
    import sys

    name = sys.argv[1] if len(sys.argv) > 1 else "Tadao Ando"
    max_p = int(sys.argv[2]) if len(sys.argv) > 2 else 5

    print(f"搜索建筑师: {name}")
    result = search_by_name(name, max_projects=max_p)

    print(f"\n建筑师: {result['architect']['name']}")
    print(f"  QID: {result['architect']['qid']}")
    print(f"  出生: {result['architect']['birth']}")
    print(f"  国家: {result['architect']['country']}")
    print(f"\n代表作品 ({len(result['projects'])} 件):")
    for i, proj in enumerate(result["projects"], 1):
        print(f"  {i}. {proj['name']} ({proj['year']}) — {proj['location']} [{proj['qid']}]")

    path = save_architect_json(result)
    print(f"\n已保存: {path}")
