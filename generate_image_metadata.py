"""
generate_image_metadata.py — 从 Qwen-VL 分析结果自动生成图片 metadata

读取: output/json/{architect}/{case}_案例分析.json 中的 vision 数据
写出: ArchAI_Image_DB/metadata/{case}_{image}.json
汇总: ArchAI_Image_DB/image_index.json

用法:
  python generate_image_metadata.py                    # 全部案例
  python generate_image_metadata.py --case 光之教堂    # 单个案例
"""

import argparse
import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

BASE = Path(__file__).resolve().parent
JSON_DIR = BASE / "output" / "json"
IMAGES_DIR = BASE / "images"
OUT_DIR = BASE / "ArchAI_Image_DB"

# 案例映射: (architect_dir, case_en, case_cn)
CASES = [
    ("Tadao_Ando", "Church_of_the_Light", "光之教堂"),
    ("Le_Corbusier", "Villa_Savoye", "萨伏伊别墅"),
    ("Louis_Kahn", "Kimbell_Art_Museum", "金贝尔艺术博物馆"),
    ("Mies_van_der_Rohe", "Barcelona_Pavilion", "巴塞罗那德国馆"),
    ("Peter_Zumthor", "Therme_Vals", "瓦尔斯温泉浴场"),
]

# 建筑师中英文
ARCHITECTS = {
    "Tadao_Ando": ("安藤忠雄", "Tadao Ando"),
    "Le_Corbusier": ("勒·柯布西耶", "Le Corbusier"),
    "Louis_Kahn": ("路易斯·康", "Louis Kahn"),
    "Mies_van_der_Rohe": ("密斯·凡德罗", "Mies van der Rohe"),
    "Peter_Zumthor": ("彼得·卒姆托", "Peter Zumthor"),
}


def extract_analysis_text(vision_text: str) -> str:
    """提取 Qwen-VL 分析文本（去除 markdown 标题和字段名）"""
    if not vision_text:
        return ""
    # 提取各字段内容
    result = {}
    # 按 **字段名：** 分割
    pattern = r"\*\*([^*]+?)[：:]\*\*\s*([^*]+?)(?=\n\*\*|\n###|\Z)"
    for match in re.finditer(pattern, vision_text):
        field = match.group(1).strip()
        content = match.group(2).strip()
        result[field] = content
    return json.dumps(result, ensure_ascii=False)


def detect_image_type(filename: str, vision_result: dict) -> str:
    """根据文件名和 vision 结构判断图片类型"""
    name_lower = filename.lower()
    if "plan" in name_lower or "平面" in name_lower:
        return "plan"
    if "section" in name_lower or "剖面" in name_lower:
        return "section"
    if "interior" in name_lower or "室内" in name_lower:
        return "space_photo"
    if "exterior" in name_lower or "外观" in name_lower:
        return "exterior"
    return "space_photo"


def build_metadata(
    image_id: str,
    filename: str,
    case_cn: str,
    case_en: str,
    architect_cn: str,
    architect_en: str,
    image_type: str,
    analysis_text: str,
    description: str,
    tags: list[str],
    design_topics: list[str],
    design_transfer: list[str],
    recommended_usage: str,
    source: dict,
) -> dict:
    """构建单张图片的 metadata"""
    return {
        "image_id": image_id,
        "filename": filename,
        "path": f"images/{case_en}/{filename}",
        "case": case_cn,
        "case_en": case_en,
        "architect": architect_cn,
        "architect_en": architect_en,
        "image_type": image_type,
        "tags": tags,
        "design_topics": design_topics,
        "design_transfer": design_transfer,
        "description": description,
        "recommended_usage": recommended_usage,
        "analysis": analysis_text,
        "source": source,
    }


def generate_case(architect_dir: str, case_en: str, case_cn: str) -> list[dict]:
    """生成一个案例所有图片的 metadata"""
    json_path = JSON_DIR / architect_dir / f"{case_cn}_案例分析.json"
    if not json_path.exists():
        print(f"  [SKIP] No JSON: {json_path}")
        return []

    full = json.loads(json_path.read_text(encoding="utf-8"))
    vision = full.get("vision", {})
    if not vision:
        print(f"  [SKIP] No vision data: {case_cn}")
        return []

    arch_cn, arch_en = ARCHITECTS.get(architect_dir, (case_cn, case_en))

    # 图片来源（从 sources 提取第一个来源）
    sources = full.get("sources", [])
    source_info = {"type": "website", "name": "", "url": ""}
    if sources:
        url = sources[0].get("url", "")
        source_info["url"] = url
        # 简化域名作为 name
        domain = re.sub(r"https?://(www\.)?", "", url).split("/")[0]
        source_info["name"] = domain

    metadata_list = []

    # Plan analysis
    if vision.get("plan_analysis"):
        meta = build_metadata(
            image_id=f"{case_en.lower().replace(' ', '_')}_plan",
            filename="plan.jpg",
            case_cn=case_cn,
            case_en=case_en,
            architect_cn=arch_cn,
            architect_en=arch_en,
            image_type="plan",
            analysis_text=vision["plan_analysis"],
            description=f"{case_cn}平面图",
            tags=["geometry", "circulation", "spatial_sequence"],
            design_topics=["空间组织", "平面布局"],
            design_transfer=[],
            recommended_usage="用于分析平面组织逻辑、空间序列和功能分区",
            source=source_info,
        )
        metadata_list.append(meta)

    # Section analysis
    if vision.get("section_analysis"):
        meta = build_metadata(
            image_id=f"{case_en.lower().replace(' ', '_')}_section",
            filename="section.jpg",
            case_cn=case_cn,
            case_en=case_en,
            architect_cn=arch_cn,
            architect_en=arch_en,
            image_type="section",
            analysis_text=vision["section_analysis"],
            description=f"{case_cn}剖面图",
            tags=["section", "light_path", "vertical_sequence"],
            design_topics=["空间序列", "剖面关系", "光路径"],
            design_transfer=[],
            recommended_usage="用于分析空间高度关系、光线进入路径和结构表达",
            source=source_info,
        )
        metadata_list.append(meta)

    # Photo analyses
    for i, pa in enumerate(vision.get("photo_analyses", []), 1):
        filename = pa.get("image", f"space_{i:02d}.jpg")
        image_type = detect_image_type(filename, vision)
        meta = build_metadata(
            image_id=f"{case_en.lower().replace(' ', '_')}_{filename.split('.')[0].replace('-', '_')}",
            filename=filename,
            case_cn=case_cn,
            case_en=case_en,
            architect_cn=arch_cn,
            architect_en=arch_en,
            image_type=image_type,
            analysis_text=pa.get("analysis", ""),
            description=f"{case_cn}空间照片",
            tags=["space_photo", "material", "atmosphere"],
            design_topics=["空间体验", "材料表达"],
            design_transfer=[],
            recommended_usage="用于分析空间氛围、材料质感和光影关系",
            source=source_info,
        )
        metadata_list.append(meta)

    return metadata_list


def enrich_with_human(metadata: dict) -> dict:
    """
    人工审校补充（第一阶段模板用）。
    为每张图片补充设计迁移场景、更精确的描述。
    """
    # 依据案例类型和图片类型补充 design_transfer
    case_type_map = {
        "Church_of_the_Light": ("纪念空间", "冥想空间", "小型宗教空间"),
        "Villa_Savoye": ("住宅设计", "坡地建筑", "现代主义空间"),
        "Kimbell_Art_Museum": ("博物馆", "展厅空间", "顶部采光建筑"),
        "Barcelona_Pavilion": ("展览空间", "材料表现空间", "流动空间"),
        "Therme_Vals": ("休闲空间", "材料感知空间", "水疗建筑"),
    }
    case_en = metadata.get("case_en", "")
    if case_en in case_type_map:
        metadata["design_transfer"] = list(case_type_map[case_en])

    # 依据图片类型细化描述
    image_type = metadata.get("image_type", "")
    case_cn = metadata.get("case", "")
    if image_type == "plan":
        metadata["description"] = f"{case_cn}平面图，展示空间组织与功能分区关系"
        metadata["recommended_usage"] = "用于分析平面组织逻辑、空间序列和功能分区"
    elif image_type == "section":
        metadata["description"] = f"{case_cn}剖面图，展示空间高度关系与光线路径"
        metadata["recommended_usage"] = "用于分析空间序列、光路径和结构表达"
    else:
        metadata["description"] = f"{case_cn}空间照片，展示空间氛围与材料质感"
        metadata["recommended_usage"] = "用于分析空间氛围、光影关系和材料表现"

    return metadata


def main():
    parser = argparse.ArgumentParser(description="Generate image metadata")
    parser.add_argument("--case", help="案例中文名（如 光之教堂）")
    parser.add_argument("--human", action="store_true", help="应用人工审校补充")
    args = parser.parse_args()

    out_dir = OUT_DIR / "metadata"
    out_dir.mkdir(parents=True, exist_ok=True)

    all_metadata = []

    for architect_dir, case_en, case_cn in CASES:
        if args.case and args.case != case_cn:
            continue

        print(f"\n=== {case_cn} ({case_en}) ===")
        metas = generate_case(architect_dir, case_en, case_cn)
        if not metas:
            print(f"  No metadata generated")
            continue

        for meta in metas:
            if args.human:
                meta = enrich_with_human(meta)

            # 写单个 metadata 文件
            fname = f"{case_en}_{meta['filename'].split('.')[0]}.json"
            path = out_dir / fname
            path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"  [OK] {fname}")
            all_metadata.append(meta)

    # 生成全局 index
    index_path = OUT_DIR / "image_index.json"
    index_data = {
        "version": "0.1",
        "total_images": len(all_metadata),
        "generated_at": "2026-08-06",
        "images": all_metadata,
    }
    index_path.write_text(json.dumps(index_data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n=== 全局索引 ===")
    print(f"  Total images: {len(all_metadata)}")
    print(f"  Index: {index_path}")


if __name__ == "__main__":
    main()
