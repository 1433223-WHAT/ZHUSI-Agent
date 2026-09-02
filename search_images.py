"""
search_images.py — ArchAI Image DB 检索函数

供 ArchAI Agent 调用，根据用户设计问题匹配相关建筑图片。
与前端 demo/index.html 的 searchImages() 逻辑保持一致。

匹配优先级（规格 v0.2）:
  0. 案例名 / 建筑师名直匹配（用户点名案例时强优先）
  1. 图片类型匹配（用户要"平面图"→plan）
  2. design_transfer（设计场景: 纪念空间、冥想空间...）× 3
  3. design_topics（建筑主题: 光环境、空间序列...）× 2
  4. tags（技术关键词: natural_light、light_path...）× 1
  5. 设计任务 boost（用户"设计XX"→优先分析图/示意逻辑图）
  6. 案例多样性去重（同一案例最多 2 张）
"""

import json
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
INDEX_PATH = BASE / "ArchAI_Image_DB" / "image_index.json"

# 中文建筑概念 → 关键词映射（三层：tags 技术词 / topics 主题词 / transfer 场景词）
CONCEPT_MAP = {
    # ── 光环境 ──────────────────────────────────────────
    "自然光": {"tags": ["natural_light", "light"]},
    "光": {"tags": ["natural_light", "light", "light_shadow"]},
    "采光": {"tags": ["natural_light", "light", "top_light"]},
    "光影": {"tags": ["light_shadow", "natural_light"]},
    "光环境": {"tags": ["natural_light", "light"], "topics": ["光环境"]},
    "明暗对比": {"topics": ["明暗对比"], "tags": ["light_shadow", "contrast"]},
    "单一光源": {"topics": ["单一光源"]},
    "光路径": {"tags": ["light_path"], "topics": ["光路径"]},
    "光线": {"tags": ["light", "natural_light"]},
    "明亮": {"tags": ["light", "natural_light"]},
    "暗": {"topics": ["明暗对比"], "tags": ["contrast"]},
    # ── 材料 ────────────────────────────────────────────
    "材料": {"tags": ["material", "concrete", "texture"]},
    "混凝土": {"tags": ["concrete"]},
    "清水混凝土": {"tags": ["concrete"], "topics": ["清水混凝土"]},
    "质感": {"tags": ["material", "texture"]},
    "材料表达": {"tags": ["material", "texture"], "topics": ["材料表达"]},
    "材料与光": {"topics": ["材料与光协同"], "tags": ["material", "light"]},
    # ── 空间 ────────────────────────────────────────────
    "空间组织": {"tags": ["geometry", "circulation", "spatial_sequence"], "topics": ["空间组织"]},
    "空间序列": {"tags": ["spatial_sequence", "circulation"], "topics": ["空间序列"]},
    "平面组织": {"topics": ["空间组织", "平面布局"], "tags": ["geometry"]},
    "平面图": {"topics": ["平面布局"], "tags": ["geometry"]},
    "动线": {"tags": ["circulation", "spatial_sequence"], "topics": ["动线分析"]},
    "流线": {"tags": ["circulation"]},
    "几何": {"tags": ["geometry"]},
    "布局": {"tags": ["geometry", "circulation"]},
    "体量": {"topics": ["体量组合"], "tags": ["geometry"]},
    "剖面": {"tags": ["section", "vertical_sequence", "light_path"], "topics": ["剖面关系"]},
    "高度": {"tags": ["section", "vertical_sequence"]},
    "压缩释放": {"topics": ["压缩释放"], "tags": ["compression"]},
    "序列": {"topics": ["空间序列"], "tags": ["spatial_sequence"]},
    # ── 氛围 / 体验 ────────────────────────────────────
    "氛围": {"tags": ["atmosphere", "space_photo"]},
    "精神": {"tags": ["spiritual_space", "atmosphere"], "topics": ["精神性空间", "空间体验"]},
    "精神性": {"tags": ["spiritual_space", "atmosphere"], "topics": ["精神性空间", "空间体验"]},
    "精神性空间": {"topics": ["精神性空间", "空间体验"]},
    "神圣": {"tags": ["spiritual_space", "atmosphere"], "topics": ["精神性空间"]},
    "安静": {"tags": ["atmosphere"]},
    "静谧": {"tags": ["atmosphere"]},
    "内省": {"tags": ["atmosphere", "spiritual_space"]},
    "空间体验": {"topics": ["空间体验"], "tags": ["experience", "atmosphere"]},
    "叙事": {"topics": ["空间叙事"]},
    # ── 设计场景（迁移）───────────────────────────────
    "纪念馆": {"topics": ["精神性空间"], "transfer": ["纪念空间", "冥想空间"]},
    "纪念": {"topics": ["精神性空间"], "transfer": ["纪念空间", "冥想空间"]},
    "纪念建筑": {"transfer": ["纪念空间"]},
    "冥想": {"transfer": ["冥想空间"]},
    "冥想空间": {"transfer": ["冥想空间"]},
    "展览": {"transfer": ["展览空间"]},
    "展厅": {"transfer": ["展览空间"]},
    "博物馆": {"tags": ["museum"], "transfer": ["博物馆"]},
    "公共建筑": {"transfer": ["小型公共建筑"]},
    "宗教": {"tags": ["spiritual_space"], "transfer": ["宗教空间"]},
    "教堂": {"transfer": ["宗教空间"]},
    "住宅": {"tags": ["residential"], "transfer": ["住宅设计"]},
    "屋顶": {"tags": ["roof", "top_light"]},
    "水疗": {"tags": ["spa", "water"]},
    "休闲": {"tags": ["spa", "relaxation"]},
    # ── 设计任务 ────────────────────────────────────────
    "设计": {"topics": ["空间组织", "空间序列"]},
    "方案": {"topics": ["空间组织", "空间序列"]},
}


def load_index() -> dict:
    """加载 image_index.json"""
    if not INDEX_PATH.exists():
        raise FileNotFoundError(f"Image index not found: {INDEX_PATH}")
    return json.loads(INDEX_PATH.read_text(encoding="utf-8"))


def _match_score(meta: dict, keywords: list[str], field: str) -> int:
    """计算单字段匹配得分（子串双向匹配，支持中文同义）"""
    if not keywords:
        return 0
    values = meta.get(field, []) or []
    score = 0
    for kw in keywords:
        for v in values:
            if kw.lower() in str(v).lower() or str(v).lower() in kw.lower():
                score += 1
    return score


def _case_hit(case_cn: str, case_en: str, query: str) -> bool:
    """判断案例名是否被查询点名（含简称匹配）。

    支持：
    - 英文案例名（case_en）子串匹配
    - 中文案例名（case_cn）子串匹配
    - 简称：案例名去掉"艺术博物馆/别墅/教堂"等后缀后出现在查询中
      （如"金贝尔" ⊂ "金贝尔艺术博物馆"）
    """
    if case_en and case_en.lower() in query.lower():
        return True
    if case_cn and case_cn in query:
        return True
    if case_cn:
        for suffix in ("艺术博物馆", "德国馆", "温泉浴场", "长屋", "别墅", "教堂"):
            if case_cn.endswith(suffix):
                short = case_cn[: -len(suffix)]
                if len(short) >= 2 and short in query:
                    return True
    return False


def search_images(query: str, top_n: int = 4) -> list[dict]:
    """
    根据用户设计问题检索匹配图片。

    Args:
        query: 用户问题（中文）
        top_n: 返回 Top-N 张图片

    Returns:
        按匹配度排序的图片 metadata 列表（含 _match_score）
    """
    index = load_index()
    images = index.get("images", [])

    query = query.strip()
    if not query:
        return []

    # ── 解析查询 → 三层关键词（tags / topics / transfer）──
    tag_keywords = []
    topic_keywords = []
    transfer_keywords = []
    for concept, mapping in CONCEPT_MAP.items():
        if concept in query:
            tag_keywords.extend(mapping.get("tags", []))
            topic_keywords.extend(mapping.get("topics", []))
            transfer_keywords.extend(mapping.get("transfer", []))

    # 整句兜底：如果没有任何概念命中，用整句作为主题词
    if not topic_keywords and not transfer_keywords:
        topic_keywords.append(query)

    scored = []
    for img in images:
        score = 0

        # 第 0 层：案例名直匹配（用户点名案例时强优先）
        # 支持简称：案例名去掉"艺术博物馆"等后缀后若出现在查询中，也算点名
        case_cn = img.get("case", "")
        case_en = img.get("case_en", "")
        if _case_hit(case_cn, case_en, query):
            score += 100

        # 建筑师名匹配
        architect = img.get("architect", "")
        if architect and architect in query:
            score += 50

        # 图片类型匹配（用户要特定图纸类型）
        itype = img.get("image_type", "")
        if "平面图" in query and itype == "plan":
            score += 30
        if "剖面图" in query and itype == "section":
            score += 30
        if ("照片" in query or "内部" in query or "实景" in query) and itype == "space_photo":
            score += 15

        # 设计任务 boost：用户要"设计XX" → 优先分析图/示意逻辑图
        is_design_task = ("设计" in query or "方案" in query or "帮我做" in query)
        if is_design_task and itype == "analysis_diagram":
            score += 20

        # 三层语义匹配
        score += _match_score(img, transfer_keywords, "design_transfer") * 3
        score += _match_score(img, topic_keywords, "design_topics") * 2
        score += _match_score(img, tag_keywords, "tags") * 1
        # 空间策略层（分析图增强字段）
        score += _match_score(img, topic_keywords, "spatial_strategy") * 2

        if score > 0:
            scored.append((score, img))

    # 按得分排序
    scored.sort(key=lambda x: x[0], reverse=True)

    # ── 案例多样性去重 ──────────────────────────────────
    # 查询中命中的案例名（点名案例）优先为其图片留位置
    # 单案例查询：该案例图填满 topN；多案例查询（比较）：按案例均衡分配
    # 其余案例每例最多 2 张，保证多样性
    named_cases = set()
    for _, img in scored:
        if _case_hit(img.get("case", ""), img.get("case_en", ""), query):
            named_cases.add(img.get("case_en") or img.get("case") or "?")

    case_count = {}
    diversified = []
    for s, img in scored:
        key = img.get("case_en") or img.get("case") or "?"
        count = case_count.get(key, 0)
        if key in named_cases:
            # 点名案例：单案例时填满 topN；多案例时按案例数均分
            cap = top_n if len(named_cases) == 1 else max(2, top_n // len(named_cases))
        else:
            cap = 2  # 非点名案例最多 2 张
        if count < cap:
            case_count[key] = count + 1
            diversified.append((s, img))
        if len(diversified) >= top_n:
            break

    # 去重后不足 topN，补充分数最高的
    if len(diversified) < top_n:
        for s, img in scored:
            if all(img["image_id"] != i["image_id"] for _, i in diversified):
                diversified.append((s, img))
                if len(diversified) >= top_n:
                    break

    results = [dict(img) for _, img in diversified]
    for (s, img), res in zip(diversified, results):
        res["_match_score"] = s

    return results


def search_by_type(image_type: str, top_n: int = 10) -> list[dict]:
    """按图片类型检索（plan / section / space_photo / analysis_diagram）"""
    index = load_index()
    images = index.get("images", [])
    return [i for i in images if i.get("image_type") == image_type][:top_n]


def search_by_case(case: str) -> list[dict]:
    """按案例检索"""
    index = load_index()
    images = index.get("images", [])
    return [i for i in images if case in i.get("case", "") or case in i.get("case_en", "")]


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Search ArchAI Image DB")
    parser.add_argument("query", nargs="?", default="", help="检索关键词")
    parser.add_argument("--type", default="", help="按图片类型筛选")
    parser.add_argument("--case", default="", help="按案例筛选")
    args = parser.parse_args()

    if args.case:
        results = search_by_case(args.case)
        print(f"案例 '{args.case}' 图片 ({len(results)} 张):")
        for r in results:
            print(f"  {r['image_id']}: {r['description']}")
    elif args.type:
        results = search_by_type(args.type)
        print(f"类型 '{args.type}' 图片 ({len(results)} 张):")
        for r in results:
            print(f"  {r['image_id']}")
    elif args.query:
        results = search_images(args.query)
        print(f"检索 '{args.query}' → {len(results)} 张:")
        for r in results:
            print(f"  [{r.get('_match_score', 0)}分] {r['image_id']} — {r['description']}")
            print(f"      路径: {r['path']}")
            if r.get('design_transfer'):
                print(f"      迁移: {r['design_transfer']}")
    else:
        print("用法: python search_images.py <关键词> [--type plan|section|space_photo|analysis_diagram] [--case 光之教堂]")
