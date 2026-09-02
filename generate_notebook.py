"""Generate main.ipynb from structured cell definitions."""
import json
from pathlib import Path

cells = []


def md(source):
    cells.append({"cell_type": "markdown", "metadata": {}, "source": [source]})


def code(source):
    cells.append({"cell_type": "code", "metadata": {}, "source": [source]})


# ── Title ──
md("""# 🏛 ArchAI Knowledge Base Generator v0.1

**建筑知识库自动生成器 — Colab 版本**

输入建筑师名字 → 自动生成 Dify 可用的建筑案例知识文件""")

# ── 0. Setup ──
md("""---
## 0. 环境配置""")

code("""# @title 安装依赖
!pip install -q openai requests beautifulsoup4 duckduckgo-search lxml""")

code("""# @title 配置 API Key
import os
from google.colab import userdata

# DeepSeek API（必须）
os.environ["DEEPSEEK_API_KEY"] = userdata.get("DEEPSEEK_API_KEY")

# Firecrawl API（可选备用）
# os.environ["FIRECRAWL_API_KEY"] = userdata.get("FIRECRAWL_API_KEY")

print("✅ API 配置完成")""")

code("""# @title 挂载 Google Drive（可选，用于持久化输出）
from google.colab import drive
drive.mount("/content/drive")

import os
OUTPUT_BASE = "/content/drive/MyDrive/ArchAI_Builder"
os.makedirs(OUTPUT_BASE, exist_ok=True)
os.makedirs(f"{OUTPUT_BASE}/output/markdown", exist_ok=True)
os.makedirs(f"{OUTPUT_BASE}/output/json", exist_ok=True)
os.makedirs(f"{OUTPUT_BASE}/data/raw", exist_ok=True)
os.makedirs(f"{OUTPUT_BASE}/data/json", exist_ok=True)
print(f"✅ 输出目录: {OUTPUT_BASE}")""")

# ── 1. Architect Discovery ──
md("""---
## 1. 建筑师发现（Wikidata）""")

code("""# @title 定义 architect 核心函数
import requests, json, re, time
from urllib.parse import quote

WIKIDATA_SPARQL = "https://query.wikidata.org/sparql"
HEADERS = {"User-Agent": "ArchAI-Knowledge-Builder/0.1", "Accept": "application/json"}

def search_architect(name, lang="zh"):
    query = f\"\"\"
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
    \"\"\"
    resp = requests.get(f"{WIKIDATA_SPARQL}?format=json&query={quote(query)}", headers=HEADERS, timeout=30)
    data = resp.json()
    bindings = data.get("results", {}).get("bindings", [])
    if not bindings:
        return None
    b = bindings[0]
    return {
        "name": b.get("architectLabel", {}).get("value", name),
        "qid": b.get("architect", {}).get("value", "").rsplit("/", 1)[-1],
        "birth": b.get("birthDate", {}).get("value", "")[:4] if "birthDate" in b else "",
        "country": b.get("countryLabel", {}).get("value", ""),
    }

def get_projects(architect_qid, max_projects=5, lang="zh"):
    query = f\"\"\"
    SELECT DISTINCT ?project ?projectLabel ?year ?location ?locationLabel WHERE {{
      ?project wdt:P84 wd:{architect_qid}.
      OPTIONAL {{ ?project wdt:P571 ?inception. BIND(YEAR(?inception) AS ?year) }}
      OPTIONAL {{ ?project wdt:P276 ?location. }}
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "{lang},en,ja". }}
    }}
    ORDER BY DESC(?year)
    LIMIT {max_projects * 2}
    \"\"\"
    resp = requests.get(f"{WIKIDATA_SPARQL}?format=json&query={quote(query)}", headers=HEADERS, timeout=30)
    data = resp.json()
    bindings = data.get("results", {}).get("bindings", [])
    seen = set()
    projects = []
    for b in bindings:
        name = b.get("projectLabel", {}).get("value", "")
        if not name:
            name = b.get("project", {}).get("value", "").rsplit("/", 1)[-1]
        nl = name.lower()
        if nl in seen:
            continue
        seen.add(nl)
        projects.append({
            "name": name,
            "qid": b.get("project", {}).get("value", "").rsplit("/", 1)[-1],
            "year": b.get("year", {}).get("value", ""),
            "location": b.get("locationLabel", {}).get("value", ""),
        })
    return projects[:max_projects]

print("✅ architect 模块就绪")""")

code("""# @title 运行：搜索建筑师
ARCHITECT_NAME = "Tadao Ando"  # @param {type:"string"}
MAX_PROJECTS = 5  # @param {type:"slider", min:1, max:10, step:1}

architect = search_architect(ARCHITECT_NAME)
if architect:
    print(f"建筑师: {architect['name']}")
    print(f"  Wikidata QID: {architect['qid']}")
    print(f"  出生: {architect['birth']}")
    print(f"  国家: {architect['country']}")
    projects = get_projects(architect["qid"], MAX_PROJECTS)
    print(f"\\n代表作品 ({len(projects)} 件):")
    for i, p in enumerate(projects, 1):
        print(f"  {i}. {p['name']} ({p['year']}) — {p['location']} [{p['qid']}]")
else:
    print(f"❌ 未找到: {ARCHITECT_NAME}")
    projects = []""")

# ── 2. Crawl ──
md("""---
## 2. 资料采集（搜索 + 抓取 + 清洗）""")

code("""# @title 定义 crawler + cleaner 核心函数
from pathlib import Path
from urllib.parse import urlparse
from bs4 import BeautifulSoup

SOURCE_PRIORITY = [
    "pritzkerprize.com", "archdaily.com", "dezeen.com",
    "wikipedia.org", "architectural-review.com", "designboom.com"
]

def rank_urls(urls):
    scored = []
    for url in urls:
        domain = urlparse(url).netloc.lower().replace("www.", "")
        score = next((i for i, k in enumerate(SOURCE_PRIORITY) if k in domain), 999)
        scored.append((score, url))
    return [u for _, u in sorted(scored)]

def search_ddg(query, max_results=10):
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            return [{"title": r.get("title",""), "url": r.get("href",""), "snippet": r.get("body","")}
                    for r in ddgs.text(query, max_results=max_results)]
    except:
        url = "https://html.duckduckgo.com/html/"
        h = {"User-Agent": "Mozilla/5.0"}
        r = requests.post(url, data={"q": query}, headers=h, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        results = []
        for item in soup.select(".result")[:max_results]:
            link = item.select_one(".result__a")
            snip = item.select_one(".result__snippet")
            if link and link.get("href"):
                results.append({"title": link.get_text(strip=True), "url": link["href"], "snippet": snip.get_text(strip=True) if snip else ""})
        return results

def fetch_page(url, timeout=20):
    h = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    r = requests.get(url, headers=h, timeout=timeout)
    r.encoding = r.apparent_encoding or "utf-8"
    soup = BeautifulSoup(r.text, "html.parser")
    for t in soup(["script","style","nav","footer","header","aside"]):
        t.decompose()
    main = soup.find("main") or soup.find("article") or soup.body
    if not main: return ""
    parts = []
    for tag in main.find_all(["h1","h2","h3","h4","p","li"]):
        text = tag.get_text(strip=True)
        if text and len(text) > 10:
            parts.append(text)
    return "\\n\\n".join(parts)

def clean_text(text):
    lines = text.split("\\n")
    cleaned = []
    noise = [r"^(menu|navigation|search|share|subscribe|log in|login|sign up)$",
             r"^(广告|导航|搜索|分享|订阅|注册|登录|评论|版权)$",
             r"^(related|recommended|popular|trending|read more)"]
    for line in lines:
        s = line.strip()
        if not s or len(s) < 15:
            continue
        if any(re.match(p, s, re.I) for p in noise):
            continue
        cleaned.append(s)
    return "\\n\\n".join(cleaned)

print("✅ crawler + cleaner 模块就绪")""")

code("""# @title 运行：搜索并抓取网页资料
TARGET_BUILDING = "Church of the Light"  # @param {type:"string"}
ARCHITECT_FOR_SEARCH = "Tadao Ando"  # @param {type:"string"}

print(f"搜索: {TARGET_BUILDING}")
queries = [
    f"{ARCHITECT_FOR_SEARCH} {TARGET_BUILDING}",
    f"{TARGET_BUILDING} architecture analysis",
]

all_results = []
seen = set()
for q in queries:
    try:
        results = search_ddg(q, max_results=8)
        for r in results:
            if r["url"] not in seen:
                seen.add(r["url"]); all_results.append(r)
        time.sleep(1)
    except Exception as e:
        print(f"  搜索失败: {e}")

print(f"找到 {len(all_results)} 个结果")
ranked = rank_urls([r["url"] for r in all_results])[:3]
selected = [r for url in ranked for r in all_results if r["url"] == url]

sources = []
for i, item in enumerate(selected):
    domain = urlparse(item["url"]).netloc.replace("www.", "")
    print(f"  [{i+1}/{len(selected)}] {domain}")
    try:
        text = fetch_page(item["url"])
        if text and len(text) > 500:
            cleaned = clean_text(text)
            sources.append({"url": item["url"], "title": item["title"], "text": cleaned})
            safe = re.sub(r'[^\\w\\-]', '_', TARGET_BUILDING)
            path = f"{OUTPUT_BASE}/data/raw/{safe}_source{i+1}.txt"
            Path(path).write_text(f"# {item['title']}\\n# {item['url']}\\n\\n{cleaned}", encoding="utf-8")
            print(f"    ✅ {len(cleaned)} 字符")
        else:
            print(f"    ⚠ 内容过短，跳过")
    except Exception as e:
        print(f"    ✗ {e}")
    time.sleep(1)

combined_text = "\\n\\n---\\n\\n".join(f"来源: {s['url']}\\n{s['text']}" for s in sources)
print(f"\\n✅ 成功抓取 {len(sources)} 个来源，共 {len(combined_text)} 字符")""")

# ── 3. Analyze ──
md("""---
## 3. AI 分析（DeepSeek 三阶段流水线）""")

code("""# @title 定义 analyzer 核心函数
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_URL = "https://api.deepseek.com/v1/chat/completions"

def call_deepseek(system_prompt, user_message, temperature=0.3):
    headers = {"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"}
    payload = {"model": "deepseek-chat", "messages": [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message}
    ], "temperature": temperature, "max_tokens": 4096}
    resp = requests.post(DEEPSEEK_URL, headers=headers, json=payload, timeout=120)
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]

def extract_json(text):
    text = text.strip()
    try: return json.loads(text)
    except: pass
    m = re.search(r"```(?:json)?\\s*\\n?(.*?)\\n?```", text, re.DOTALL)
    if m:
        try: return json.loads(m.group(1).strip())
        except: pass
    s = text.find("{"); e = text.rfind("}")
    if s != -1 and e != -1:
        try: return json.loads(text[s:e+1])
        except: pass
    raise ValueError(f"无法解析 JSON: {text[:300]}")

EXTRACT_PROMPT = \"\"\"你是建筑资料整理专家。从给定文本提取结构化事实。只提取原文明确出现的信息，绝不编造。
输出 JSON：
{
  "basic_info": {"name_cn":"","name_en":"","architect":"","year":"","location":"","type":"","area":""},
  "materials": [], "structure": "",
  "spatial_features": [{"feature":"","source":""}],
  "light_strategy": {"description":"","source":""},
  "facts": [{"category":"","content":"","source":""}],
  "completeness": {"basic_info":"完整/部分/不足","spatial":"","material":"","light":""}
}\"\"\"

ANALYZE_PROMPT = \"\"\"你是建筑教育专家。基于事实 JSON 进行教学分析。
**防幻觉规则：**
1. 所有分析必须基于提供的事实
2. 每条结论标注来源事实
3. 无法从事实判断 → 标记"资料不足，无法判断"
4. 禁止使用"可能""或许""据推测""一般认为"
输出 JSON：
{
  "design_concept": {"summary":"","keywords":[],"analysis":"","source_facts":[]},
  "spatial_analysis": {"layout":"","circulation":"","experience":"","keywords":[],"source_facts":[]},
  "material_analysis": {"materials_used":[],"material_logic":"","material_space_relationship":"","keywords":[],"source_facts":[]},
  "light_analysis": {"strategy":"","effect":"","keywords":[],"source_facts":[]},
  "teaching_value": {
    "design_strategies": [{"strategy":"","application_scenario":"","source_facts":[]}],
    "learning_points": [{"point":"","why_important":""}]
  },
  "data_gaps": []
}\"\"\"

GENERATE_PROMPT = \"\"\"你是建筑知识库编辑。整合事实和分析，生成 Dify 优化 Markdown。
模板结构：
# {名称}
## 基本信息（建筑师/时间/地点/类型/材料）
## 设计理念（关键词 + 内容）
## 空间组织（关键词 + 内容）
## 材料与构造（关键词 + 内容）
## 光环境（关键词 + 内容）
## 可迁移设计策略（适用场景 + 策略列表）
## 对学生设计的启发
## 来源
注意：每个 ## 章节包含"关键词："行，方便 Dify 向量检索匹配。\"\"\"

print("✅ analyzer 模块就绪")""")

code("""# @title Stage 1: 提取事实
print("[Stage 1] 提取事实...")
user_msg = EXTRACT_PROMPT + f"\\n\\n## 输入文本\\n{combined_text}"
raw = call_deepseek("你是建筑资料整理专家。只提取原文明确信息，回复合法 JSON。", user_msg, temperature=0.1)
facts = extract_json(raw)

if not facts.get("basic_info",{}).get("name_cn"):
    facts.setdefault("basic_info",{})["name_cn"] = TARGET_BUILDING

building_name = facts["basic_info"].get("name_cn", TARGET_BUILDING)
print(f"  建筑: {building_name}")
print(f"  建筑师: {facts['basic_info'].get('architect','?')}")
print(f"  事实条目: {len(facts.get('facts',[]))}")
print(f"  完整度: {facts.get('completeness',{})}")

safe_name = re.sub(r'[^\\w\\-一-鿿]', '_', building_name)
with open(f"{OUTPUT_BASE}/data/json/{safe_name}_facts.json", "w", encoding="utf-8") as f:
    json.dump(facts, f, ensure_ascii=False, indent=2)
print("  ✅ facts.json 已保存")""")

code("""# @title Stage 2: 教学分析
print("[Stage 2] 教学分析...")
user_msg = ANALYZE_PROMPT + f"\\n\\n## 输入事实 JSON\\n{json.dumps(facts, ensure_ascii=False, indent=2)}"
raw = call_deepseek("你是建筑教育专家。所有分析基于提供的事实，绝不编造。回复合法 JSON。", user_msg, temperature=0.3)
analysis = extract_json(raw)

dc = analysis.get('design_concept',{})
print(f"  设计理念: {dc.get('summary','?')[:80]}...")
print(f"  设计策略: {len(analysis.get('teaching_value',{}).get('design_strategies',[]))} 条")
print(f"  学习要点: {len(analysis.get('teaching_value',{}).get('learning_points',[]))} 条")
print(f"  资料缺口: {len(analysis.get('data_gaps',[]))} 项")

with open(f"{OUTPUT_BASE}/data/json/{safe_name}_analysis.json", "w", encoding="utf-8") as f:
    json.dump(analysis, f, ensure_ascii=False, indent=2)
print("  ✅ analysis.json 已保存")""")

code("""# @title Stage 3: 生成知识文件
print("[Stage 3] 生成 Markdown...")
user_msg = GENERATE_PROMPT + f"\\n\\n## 事实\\n{json.dumps(facts, ensure_ascii=False, indent=2)}\\n\\n## 分析\\n{json.dumps(analysis, ensure_ascii=False, indent=2)}"
md_text = call_deepseek("你是建筑知识库编辑。生成面向 Dify 优化的 Markdown，回复纯 Markdown。", user_msg, temperature=0.4)

md_text = md_text.strip()
if md_text.startswith("```markdown"): md_text = md_text[len("```markdown"):].strip()
elif md_text.startswith("```"): md_text = md_text[3:].strip()
if md_text.endswith("```"): md_text = md_text[:-3].strip()

# 添加来源
md_text += "\\n\\n## 来源\\n"
for s in sources:
    md_text += f"- [{s['title'] or s['url']}]({s['url']})\\n"

md_path = f"{OUTPUT_BASE}/output/markdown/{safe_name}_案例分析.md"
Path(md_path).write_text(md_text, encoding="utf-8")

json_path = f"{OUTPUT_BASE}/output/json/{safe_name}_案例分析.json"
full = {"building_name": building_name, "facts": facts, "analysis": analysis, "markdown": md_text, "sources": [{"url":s["url"],"title":s["title"]} for s in sources]}
Path(json_path).write_text(json.dumps(full, ensure_ascii=False, indent=2), encoding="utf-8")

print(f"✅ Markdown: {md_path}")
print(f"✅ JSON:     {json_path}")""")

code("""# @title 📄 预览生成的 Markdown
from IPython.display import display, Markdown
display(Markdown(md_text))""")

# ── 4. Batch ──
md("""---
## 4. 批量模式（Phase 3：20位大师 × 5案例）""")

code("""# @title 批量生成知识库
ARCHITECTS = [
    "Tadao Ando",
    "Le Corbusier",
    "Louis Kahn",
    "Zaha Hadid",
    "Mies van der Rohe",
]

MAX_PROJECTS_PER = 5

for arch_name in ARCHITECTS:
    print(f"\\n{'='*60}")
    print(f"🏛 {arch_name}")
    print('='*60)
    try:
        arch = search_architect(arch_name)
        if not arch: print("  ❌ 未找到"); continue
        projs = get_projects(arch["qid"], MAX_PROJECTS_PER)
        print(f"  {len(projs)} 件作品")
        for j, proj in enumerate(projs):
            print(f"  [{j+1}/{len(projs)}] {proj['name']} ({proj['year']})")
            queries = [f"{arch_name} {proj['name']}", f"{proj['name']} architecture"]
            all_r = []; seen_u = set()
            for q in queries:
                try:
                    for r in search_ddg(q, 6):
                        if r["url"] not in seen_u: seen_u.add(r["url"]); all_r.append(r)
                    time.sleep(1)
                except: pass
            ranked = rank_urls([r["url"] for r in all_r])[:3]
            sources_b = []
            for url in ranked:
                try:
                    text = fetch_page(url)
                    if text and len(text) > 500: sources_b.append({"url": url, "title": "", "text": clean_text(text)})
                    time.sleep(1)
                except: pass
            if not sources_b: print("    ❌ 无来源"); continue
            combined = "\\n\\n---\\n\\n".join(f"来源: {s['url']}\\n{s['text']}" for s in sources_b)
            facts = extract_json(call_deepseek("提取事实，回复合法 JSON。", EXTRACT_PROMPT + f"\\n\\n## 输入\\n{combined}", 0.1))
            name_cn = facts.get("basic_info",{}).get("name_cn", proj["name"])
            analysis = extract_json(call_deepseek("教学分析，回复合法 JSON。", ANALYZE_PROMPT + f"\\n\\n## 事实\\n{json.dumps(facts, ensure_ascii=False)}", 0.3))
            md_text = call_deepseek("生成 Markdown。", GENERATE_PROMPT + f"\\n\\n## 事实\\n{json.dumps(facts, ensure_ascii=False)}\\n\\n## 分析\\n{json.dumps(analysis, ensure_ascii=False)}", 0.4)
            md_text = md_text.strip().removeprefix("```markdown").removeprefix("```").removesuffix("```").strip()
            for s in sources_b: md_text += f"\\n- [{s['url']}]({s['url']})"
            safe = re.sub(r'[^\\w\\-一-鿿]', '_', name_cn)
            Path(f"{OUTPUT_BASE}/output/markdown/{safe}_案例分析.md").write_text(md_text, encoding="utf-8")
            print(f"    ✅ {safe}_案例分析.md")
    except Exception as e:
        print(f"  ❌ {e}"); continue

print(f"\\n🎉 完成！查看: {OUTPUT_BASE}/output/markdown/")""")

# ── Footer ──
md("""---
## 📤 导入 Dify

1. 下载 `output/markdown/` 中所有 `.md` 文件
2. Dify → 知识库 → 新建 → 上传文件
3. 配置 ArchAI 助手使用该知识库
4. 测试检索：

> "小型公共空间如何利用自然光创造精神体验？"
>
> "清水混凝土在宗教建筑中如何应用？"
>
> "安藤忠雄的空间组织有什么特点？"
""")

# ── Write notebook ──
notebook = {
    "nbformat": 4,
    "nbformat_minor": 5,
    "metadata": {
        "colab": {"name": "ArchAI_Knowledge_Builder_v0.1.ipynb"},
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python", "version": "3.10.0"},
    },
    "cells": cells,
}

out = Path(__file__).resolve().parent / "main.ipynb"
out.write_text(json.dumps(notebook, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"✅ {out} ({len(cells)} cells)")
