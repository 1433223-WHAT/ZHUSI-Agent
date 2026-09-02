# -*- coding: utf-8 -*-
"""case_entities.py — 知识系统 V2.0：最小案例实体索引（第一阶段）

把「案例文本节点 + 图片目录 + 名称/别名 + 建筑师/年份/来源」挂成一个案例对象。
资产类型标注（产品原则：图片也进证据体系——区分 原始图纸 / 筑思分析图 / 空间照片）。

用法：
    find_case_entity(text)     -> 在文本中匹配案例（名称/别名），返回实体或 None
    get_case_entity(name)      -> 按名称取实体
    get_case_assets(name, kw)  -> 取实体视觉资产，可按类型关键词筛选（平面/剖面/照片/分析/光）
"""

from __future__ import annotations

import re
from pathlib import Path

BASE = Path(__file__).resolve().parent

# 案例名称/别名 → 图片目录（有视觉资产的案例）
CASE_DIR_MAP = {
    "光之教堂": "Church_of_the_Light", "Church of the Light": "Church_of_the_Light",
    "巴塞罗那德国馆": "Barcelona_Pavilion", "巴塞罗那馆": "Barcelona_Pavilion", "Barcelona Pavilion": "Barcelona_Pavilion",
    "金贝尔艺术博物馆": "Kimbell_Art_Museum", "金贝尔": "Kimbell_Art_Museum", "Kimbell": "Kimbell_Art_Museum",
    "瓦尔斯温泉浴场": "Therme_Vals", "瓦尔斯": "Therme_Vals", "Therme Vals": "Therme_Vals",
    "萨伏伊别墅": "Villa_Savoye", "萨伏伊": "Villa_Savoye", "Villa Savoye": "Villa_Savoye",
}

# 资产类型推断：文件名 → (中文类型标签, kind)  kind ∈ original(原始图纸)/analysis(筑思分析图)/photo(空间照片)
_ASSET_RULES = [
    (re.compile(r"plan_analysis"), ("平面分析图", "analysis")),
    (re.compile(r"light_path"), ("光路径分析图", "analysis")),
    (re.compile(r"spatial_sequence"), ("空间序列分析图", "analysis")),
    (re.compile(r"material_light"), ("材料与光分析图", "analysis")),
    (re.compile(r"^plan\."), ("平面图", "original")),
    (re.compile(r"^section\."), ("剖面图", "original")),
    (re.compile(r"^interior\."), ("室内照片", "photo")),
    (re.compile(r"^space_"), ("空间照片", "photo")),
    (re.compile(r"analysis|_study|_diagram"), ("分析图", "analysis")),
]

_KIND_LABEL = {"original": "原始图纸", "analysis": "筑思分析图", "photo": "空间照片"}


def classify_asset(filename: str) -> tuple[str, str]:
    """按文件名推断 (中文类型标签, kind)。"""
    for pattern, (label, kind) in _ASSET_RULES:
        if pattern.search(filename):
            return label, kind
    return "图片", "original"


# 案例基础信息（名称 → 建筑师/年份/来源），从知识库 metadata 一次性提取
_ENTITY_META: dict[str, dict] | None = None


def _load_entity_meta() -> dict[str, dict]:
    """从知识库 metadata 提取案例基础信息（case → architect/built_year/source）。"""
    global _ENTITY_META
    if _ENTITY_META is not None:
        return _ENTITY_META
    meta_map: dict[str, dict] = {}
    try:
        from local_search import _load_index
        for m in _load_index().get("metadata", []):
            if m.get("type") != "case_strategy":
                continue
            name = m.get("case", "")
            if not name or name in meta_map:
                continue
            meta_map[name] = {
                "architect": m.get("architect", ""),
                "built_year": m.get("built_year", ""),
                "source": m.get("source", ""),
            }
    except Exception:
        pass
    _ENTITY_META = meta_map
    return meta_map


def _assets_for(dirname: str) -> list[dict]:
    """读取 images/<dirname> 真实文件，生成资产列表（不编造不存在的文件）。"""
    folder = BASE / "images" / dirname
    if not folder.is_dir():
        return []
    assets = []
    for f in sorted(folder.iterdir()):
        if not f.is_file() or f.suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp"}:
            continue
        label, kind = classify_asset(f.name)
        assets.append({
            "file": f.name,
            "label": label,
            "kind": kind,
            "kind_label": _KIND_LABEL.get(kind, "图片"),
            "url": f"http://127.0.0.1:8000/images/{dirname}/{f.name}",
        })
    return assets


def _canonical_name(name: str) -> str:
    """别名 → 规范名（知识库 meta 中的名称），保证 meta 信息与 name 一致。"""
    meta = _load_entity_meta()
    if name in meta:
        return name
    dirname = CASE_DIR_MAP.get(name, "")
    if dirname:
        for n in CASE_DIR_MAP:
            if CASE_DIR_MAP[n] == dirname and n in meta:
                return n
    return name


def get_case_entity(name: str) -> dict | None:
    """按名称取案例实体（含视觉资产），别名自动归一化为规范名。"""
    name = _canonical_name(name)
    meta = _load_entity_meta()
    dirname = CASE_DIR_MAP.get(name, "")
    if name not in meta and not dirname:
        return None
    info = meta.get(name, {})
    return {
        "entity_id": f"case:{name}",
        "name": name,
        "architect": info.get("architect", ""),
        "built_year": info.get("built_year", ""),
        "source": info.get("source", ""),
        "image_dir": dirname,
        "assets": _assets_for(dirname) if dirname else [],
    }


# 案例常见别名（含省略"的"等自然说法）
_NAME_ALIASES = {
    "光之教堂": ["Church of the Light", "church of the light"],
    "巴塞罗那德国馆": ["巴塞罗那馆", "Barcelona Pavilion", "德国馆"],
    "金贝尔艺术博物馆": ["金贝尔", "Kimbell"],
    "瓦尔斯温泉浴场": ["瓦尔斯", "Therme Vals"],
    "萨伏伊别墅": ["萨伏伊", "Villa Savoye"],
    "住吉的长屋": ["住吉长屋", "Row House"],
    "天津滨海新区图书馆": ["天津滨海图书馆", "滨海图书馆", "Binhai Library"],
    "奥雷斯塔高中": ["奥雷斯塔", "Orestad Gymnasium", "Orestad"],
    "藤幼儿园": ["Fuji Kindergarten", "富士幼儿园"],
    "北京市第四中学房山校区": ["北京四中", "四中房山", "四中房山校区", "Beijing No.4 High School"],
    "三联海边图书馆": ["孤独图书馆", "三联图书馆", "海边图书馆", "阿那亚图书馆"],
    "Kids_Republic": ["Kids Republic", "儿童王国", "孩之宝"],
}


def find_case_entity(text: str) -> dict | None:
    """在文本中匹配案例（名称/别名，含英文别名），返回实体或 None。"""
    if not text:
        return None
    meta = _load_entity_meta()
    all_names = set(meta.keys()) | set(CASE_DIR_MAP.keys())
    for name in sorted(all_names, key=len, reverse=True):
        if name and name in text:
            return get_case_entity(name)
    lowered = text.lower()
    for name, aliases in _NAME_ALIASES.items():
        for alias in aliases:
            if alias.lower() in lowered:
                return get_case_entity(name)
    # 英文目录别名（大小写不敏感）
    for alias, dirname in CASE_DIR_MAP.items():
        if alias.lower() in lowered and alias not in text and alias not in _NAME_ALIASES:
            name = next((n for n, d in CASE_DIR_MAP.items() if d == dirname and n in meta), None)
            if name:
                return get_case_entity(name)
    return None


_ASSET_FILTER = [
    (re.compile(r"平面"), ("plan",)),
    (re.compile(r"剖面"), ("section",)),
    (re.compile(r"照片|空间|室内"), ("space-photo", "interior-photo", "photo")),
    (re.compile(r"分析"), ("analysis",)),
    (re.compile(r"光"), ("light",)),
]


def get_case_assets(name: str, keyword: str = "") -> list[dict]:
    """取案例视觉资产；keyword 匹配资产类型标签（平面/剖面/照片/分析/光）。"""
    entity = get_case_entity(name)
    if not entity:
        return []
    assets = entity["assets"]
    if not keyword:
        return assets
    for pattern, kinds in _ASSET_FILTER:
        if pattern.search(keyword):
            return [a for a in assets if a["kind"] in kinds or a["label"].find(keyword) >= 0]
    kw = keyword.strip()
    return [a for a in assets if kw and kw in a["label"]]
