"""
ArchAI Knowledge Base Generator — crawler.py
搜索 + 网页抓取

Uses DuckDuckGo Search API (free, no key required) for search,
BeautifulSoup for primary extraction, Firecrawl as fallback.
"""

import json
import re
import time
from pathlib import Path
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

# ── Source Ranking ────────────────────────────────────────────────────

SOURCE_PRIORITY = [
    "pritzkerprize.com",
    "archdaily.com",
    "dezeen.com",
    "wikipedia.org",
    "architectural-review.com",
    "archinect.com",
    "designboom.com",
    "archello.com",
    "architizer.com",
    "divisare.com",
]


def rank_sources(urls: list[str]) -> list[str]:
    """Sort URLs by priority: known architecture sources first."""
    scored = []
    for url in urls:
        domain = urlparse(url).netloc.lower().replace("www.", "")
        # Find the best (lowest) priority index among known domains
        score = 999
        for i, known in enumerate(SOURCE_PRIORITY):
            if known in domain:
                score = i
                break
        scored.append((score, url))
    scored.sort(key=lambda x: x[0])
    return [url for _, url in scored]


# ── DuckDuckGo Search ─────────────────────────────────────────────────

def search_ddg(query: str, max_results: int = 10) -> list[dict]:
    """
    Search DuckDuckGo (uses the HTML search, no API key needed).

    Args:
        query: Search query string
        max_results: Maximum number of results to return

    Returns:
        List of dicts with keys: title, url, snippet
    """
    # Try duckduckgo_search library first (Colab-friendly)
    try:
        from duckduckgo_search import DDGS

        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                results.append({
                    "title": r.get("title", ""),
                    "url": r.get("href", ""),
                    "snippet": r.get("body", ""),
                })
        return results
    except ImportError:
        pass

    # Fallback: direct HTML search (fragile, but works without any library)
    url = "https://html.duckduckgo.com/html/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    resp = requests.post(url, data={"q": query}, headers=headers, timeout=15)
    soup = BeautifulSoup(resp.text, "html.parser")
    results = []
    for item in soup.select(".result")[:max_results]:
        link = item.select_one(".result__a")
        snippet = item.select_one(".result__snippet")
        if link and link.get("href"):
            results.append({
                "title": link.get_text(strip=True),
                "url": link["href"],
                "snippet": snippet.get_text(strip=True) if snippet else "",
            })
    return results


# ── Web Fetch ─────────────────────────────────────────────────────────

def fetch_page(url: str, timeout: int = 20) -> str:
    """
    Fetch and extract readable text from a web page using BeautifulSoup.

    Args:
        url: Web page URL
        timeout: Request timeout in seconds

    Returns:
        Extracted clean text
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }

    resp = requests.get(url, headers=headers, timeout=timeout)
    resp.raise_for_status()

    # Detect encoding
    resp.encoding = resp.apparent_encoding or "utf-8"
    html = resp.text

    soup = BeautifulSoup(html, "html.parser")

    # Remove noise elements
    for tag in soup(["script", "style", "nav", "footer", "header", "aside",
                     "noscript", "iframe", "form", "button", "svg"]):
        tag.decompose()

    # Try to find main content area
    main = (
        soup.find("main")
        or soup.find("article")
        or soup.find(attrs={"role": "main"})
        or soup.find(class_=re.compile(r"content|article|post|entry", re.I))
        or soup.find(id=re.compile(r"content|article|post|entry", re.I))
        or soup.body
    )

    if main is None:
        return ""

    # Extract headings and paragraphs
    parts = []
    for tag in main.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "figcaption"]):
        text = tag.get_text(strip=True)
        if text and len(text) > 10:
            if tag.name.startswith("h"):
                parts.append(f"\n## {text}\n")
            else:
                parts.append(text)

    # Handle img alt text
    for img in main.find_all("img"):
        alt = img.get("alt", "").strip()
        if alt and len(alt) > 5:
            parts.append(f"[图片: {alt}]")

    return "\n\n".join(parts)


def fetch_firecrawl(url: str, api_key: str = "") -> str:
    """
    Fallback: use Firecrawl API for better extraction.

    Args:
        url: Web page URL
        api_key: Firecrawl API key

    Returns:
        Extracted markdown text
    """
    if not api_key:
        api_key = __import__("os").environ.get("FIRECRAWL_API_KEY", "")
    if not api_key:
        raise RuntimeError("Firecrawl API key 未设置")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    resp = requests.post(
        "https://api.firecrawl.dev/v1/scrape",
        headers=headers,
        json={"url": url, "formats": ["markdown"]},
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()
    return data.get("data", {}).get("markdown", "")


# ── Main crawler ──────────────────────────────────────────────────────

def search_and_fetch(
    building_name: str,
    architect_name: str = "",
    max_sources: int = 3,
    raw_dir: str | Path = "",
) -> dict:
    """
    Search for building info and fetch content from top sources.

    Args:
        building_name: Name of the building to search for
        architect_name: Optional architect name for better search queries
        max_sources: Maximum number of distinct sources to fetch
        raw_dir: Directory to save raw fetched text

    Returns:
        dict with keys: building_name, sources (list of {url, text}), combined_text
    """
    # Build search queries
    queries = [f"{building_name} architecture"]
    if architect_name:
        queries.insert(0, f"{architect_name} {building_name}")

    all_results = []
    seen_urls = set()

    for query in queries:
        try:
            results = search_ddg(query, max_results=10)
            for r in results:
                url = r.get("url", "")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    all_results.append(r)
        except Exception as e:
            print(f"  搜索失败 [{query}]: {e}")
        time.sleep(1)  # Rate limit

    if not all_results:
        raise RuntimeError(f"未找到 {building_name} 的搜索结果")

    # Rank and select top sources
    ranked_urls = rank_sources([r["url"] for r in all_results])
    selected_urls = ranked_urls[:max_sources]

    # Find the metadata for selected urls
    selected = []
    for url in selected_urls:
        for r in all_results:
            if r["url"] == url:
                selected.append(r)
                break

    print(f"  找到 {len(all_results)} 个搜索结果，选择前 {len(selected)} 个高质量来源")

    # Fetch each source
    sources = []
    for i, item in enumerate(selected):
        url = item["url"]
        domain = urlparse(url).netloc.replace("www.", "")
        print(f"  [{i+1}/{len(selected)}] 抓取: {domain}")

        try:
            text = fetch_page(url)
            if text and len(text) > 500:
                sources.append({"url": url, "title": item["title"], "text": text})
            else:
                print(f"    ⚠ 内容过短 ({len(text)} 字符), 跳过")
        except Exception as e:
            print(f"    ⚠ BeautifulSoup 失败: {e}, 尝试 Firecrawl...")
            try:
                text = fetch_firecrawl(url)
                if text and len(text) > 500:
                    sources.append({"url": url, "title": item["title"], "text": text})
                else:
                    print(f"    ⚠ Firecrawl 内容也过短, 跳过")
            except Exception as e2:
                print(f"    ✗ Firecrawl 也失败: {e2}")

        time.sleep(1)

    if not sources:
        raise RuntimeError(f"未能成功抓取任何 {building_name} 的有效内容")

    # Save raw text
    if raw_dir:
        raw_path = Path(raw_dir)
        raw_path.mkdir(parents=True, exist_ok=True)
        safe_name = re.sub(r"[^\w\-_]", "_", building_name)
        for i, src in enumerate(sources):
            filepath = raw_path / f"{safe_name}_source{i+1}.txt"
            content = f"# {src['title']}\n# URL: {src['url']}\n\n{src['text']}"
            filepath.write_text(content, encoding="utf-8")
            print(f"    已保存: {filepath}")

    # Combine all text
    combined = "\n\n---\n\n".join(
        f"来源: {s['url']}\n标题: {s['title']}\n\n{s['text']}"
        for s in sources
    )

    return {
        "building_name": building_name,
        "sources": [{"url": s["url"], "title": s["title"]} for s in sources],
        "combined_text": combined,
    }


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("用法: python crawler.py <建筑名称> [建筑师名称]")
        sys.exit(1)

    bldg = sys.argv[1]
    arch = sys.argv[2] if len(sys.argv) > 2 else ""
    result = search_and_fetch(bldg, arch, raw_dir="data/raw")
    print(f"\n✅ 抓取完成: {len(result['sources'])} 个来源, {len(result['combined_text'])} 字符")
