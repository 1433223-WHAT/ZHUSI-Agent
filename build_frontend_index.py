"""
build_frontend_index.py — 为 Demo 前端生成带 caption/reason 的 image_index.json

在 ArchAI_Image_DB/image_index.json 基础上，补充前端展示字段：
  - caption: 图片短标题（取自 description）
  - reason: 推荐理由（从 recommended_usage 提炼，或取自 analysis 的关键句）

输出: demo/../ArchAI_Image_DB/image_index.frontend.json
"""

import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

BASE = Path(__file__).resolve().parent
INDEX_PATH = BASE / "ArchAI_Image_DB" / "image_index.json"
OUT_PATH = BASE / "ArchAI_Image_DB" / "image_index.frontend.json"


def extract_reason(meta: dict) -> str:
    """从 analysis 提炼一句话推荐理由"""
    # 优先 recommended_usage
    usage = meta.get("recommended_usage", "")
    if usage:
        return usage

    # 从 analysis 提取"可迁移设计策略"第一点
    analysis = meta.get("analysis", "")
    if analysis:
        # 找策略编号
        m = re.search(r"1\.\s*\*\*([^*]+)\*\*", analysis)
        if m:
            return m.group(1).strip()

    # 从 design_topics 组合
    topics = meta.get("design_topics", [])
    if topics:
        return "涉及" + "、".join(topics)

    return "建筑空间分析参考"


def main():
    if not INDEX_PATH.exists():
        print(f"[ERROR] {INDEX_PATH} 不存在")
        return

    index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    images = index.get("images", [])

    for meta in images:
        # caption: 案例名 + 类型描述
        case = meta.get("case", "")
        itype = meta.get("image_type", "")
        type_names = {"plan": "平面图", "section": "剖面图", "space_photo": "空间照片", "exterior": "外观图"}
        type_cn = type_names.get(itype, "图片")
        meta["caption"] = f"{case} · {type_cn}"

        # reason: 推荐理由
        meta["reason"] = extract_reason(meta)

    index["frontend_fields"] = ["caption", "reason"]
    OUT_PATH.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] 生成前端索引: {OUT_PATH}")
    print(f"     {len(images)} 张图片，已补充 caption + reason")

    # 展示几条示例
    for img in images[:3]:
        print(f"\n  {img['image_id']}:")
        print(f"    caption: {img['caption']}")
        print(f"    reason:  {img['reason'][:60]}...")


if __name__ == "__main__":
    main()
