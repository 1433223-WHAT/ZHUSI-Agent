"""
enhance_with_vision.py — 为已有案例 Markdown 添加视觉分析章节

流程:
  1. 读取 output/json/{architect}/{case}_案例分析.json (含 facts + analysis)
  2. 运行 Qwen-VL 分析 images/{case}/ 下所有图片
  3. 生成带「## 视觉分析」章节的新 Markdown
  4. 保存回 output/markdown/{architect}/{case}_案例分析.md

用法:
  python enhance_with_vision.py --case "Church_of_the_Light" --architect "Tadao Ando" --name "光之教堂"
  python enhance_with_vision.py --all           # 处理 images/ 下所有已有图片的案例
"""

import argparse
import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

from modules.exporter import facts_to_markdown
from modules.vision_analyzer import run_vision_pipeline


def enhance_one_case(architect_dir: str, case_dir: str, name_cn: str) -> Path | None:
    """
    Enhance a single case with vision analysis.

    Args:
        architect_dir: Architect directory name (e.g. 'Tadao_Ando')
        case_dir: Case directory name (e.g. 'Church_of_the_Light')
        name_cn: Chinese name (e.g. '光之教堂')

    Returns:
        Path to updated markdown, or None if no images found
    """
    base = Path(__file__).resolve().parent
    image_dir = base / "images" / case_dir

    # Check images exist
    images = list(image_dir.glob("*.jpg")) + list(image_dir.glob("*.png")) + list(image_dir.glob("*.jpeg"))
    if not images:
        print(f"  [SKIP] No images in {image_dir}")
        return None

    # Load existing JSON (facts + analysis)
    json_path = base / "output" / "json" / architect_dir / f"{name_cn}_案例分析.json"
    md_path = base / "output" / "markdown" / architect_dir / f"{name_cn}_案例分析.md"

    if json_path.exists():
        full = json.loads(json_path.read_text(encoding="utf-8"))
        facts = full.get("facts", {})
        analysis = full.get("analysis", {})
        sources = full.get("sources", [])
        print(f"  [LOAD] facts + analysis from {json_path.name}")
    elif md_path.exists():
        # Fallback: reconstruct minimal facts from existing markdown
        print(f"  [WARN] No JSON found at {json_path}, using empty facts")
        facts = {"basic_info": {"name_cn": name_cn}}
        analysis = {}
        sources = []
    else:
        print(f"  [ERROR] No existing case data found for {name_cn}")
        return None

    # Run vision analysis
    print(f"  [VISION] Analyzing {len(images)} images...")
    try:
        vision = run_vision_pipeline(
            image_dir,
            building_name=name_cn,
            architect=architect_dir.replace("_", " "),
        )
    except Exception as e:
        print(f"  [ERROR] Vision analysis failed: {e}")
        return None

    # Generate enhanced markdown
    md = facts_to_markdown(
        facts,
        analysis,
        sources=sources,
        vision=vision,
        image_dir=f"images/{case_dir}",
    )

    # Save
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(md, encoding="utf-8")
    print(f"  [DONE] Updated: {md_path}")

    # Also update JSON with vision data
    if json_path.exists():
        full["vision"] = vision
        json_path.write_text(json.dumps(full, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  [DONE] Updated JSON: {json_path}")

    return md_path


def main():
    parser = argparse.ArgumentParser(description="Enhance cases with Qwen-VL vision analysis")
    parser.add_argument("--case", help="Case directory name (e.g. Church_of_the_Light)")
    parser.add_argument("--architect", help="Architect directory name (e.g. Tadao_Ando)")
    parser.add_argument("--name", help="Chinese case name (e.g. 光之教堂)")
    parser.add_argument("--all", action="store_true", help="Process all cases with images")
    args = parser.parse_args()

    if args.all:
        base = Path(__file__).resolve().parent
        images_root = base / "images"
        if not images_root.exists():
            print("[ERROR] No images/ directory")
            return

        # Map case dir -> (architect_dir, name_cn) via master_works
        from master_works import MASTER_WORKS

        case_map = {}
        for arch_name, arch_data in MASTER_WORKS.items():
            safe_arch = re.sub(r"[^\w\-_]", "_", arch_name)
            for work in arch_data["works"]:
                name_en = work["name"]
                safe_case = re.sub(r"[^\w\-_]", "_", name_en)
                case_map[safe_case] = (safe_arch, work["name_cn"])

        for case_dir in sorted(images_root.iterdir()):
            if not case_dir.is_dir():
                continue
            case_key = case_dir.name
            if case_key not in case_map:
                print(f"\n[SKIP] {case_key} — not in master_works")
                continue
            arch_dir, name_cn = case_map[case_key]
            print(f"\n{'='*50}")
            print(f"Case: {name_cn} ({case_key})")
            enhance_one_case(arch_dir, case_key, name_cn)

    elif args.case and args.architect and args.name:
        enhance_one_case(args.architect, args.case, args.name)
    else:
        print("Usage: python enhance_with_vision.py --all")
        print("   or: python enhance_with_vision.py --case Church_of_the_Light --architect Tadao_Ando --name 光之教堂")


if __name__ == "__main__":
    main()
