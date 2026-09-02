"""
ArchAI Knowledge Base Generator — vision_analyzer.py
Phase 3: Visual Knowledge Layer

Uses Qwen-VL (via DashScope API) to analyze architectural images:
  - Floor plans → spatial organization analysis
  - Sections → spatial sequence + light path analysis
  - Space photos → atmosphere + material analysis

Each analysis produces structured Chinese text for Dify knowledge base import.

API: DashScope multimodal-generation (Qwen-VL)
Docs: https://help.aliyun.com/document_detail/2712195.html
"""

import base64
import json
import os
import re
from pathlib import Path

import requests

# ── DashScope API config ─────────────────────────────────────────────
DASHSCOPE_API_KEY = os.environ.get("DASHSCOPE_API_KEY", "")
DASHSCOPE_URL = (
    "https://dashscope.aliyuncs.com/api/v1/services/aigc/"
    "multimodal-generation/generation"
)
QWEN_VL_MODEL = "qwen-vl-max"  # or qwen-vl-plus for lower cost
QWEN_VL_TIMEOUT = 120
QWEN_VL_MAX_RETRIES = 2

# Try loading from .env file if not in environment
if not DASHSCOPE_API_KEY:
    _env_path = Path(__file__).resolve().parent.parent / ".env"
    if _env_path.exists():
        with open(_env_path, "r", encoding="utf-8") as _f:
            for _line in _f:
                _line = _line.strip()
                if _line and not _line.startswith("#") and "=" in _line:
                    _k, _v = _line.split("=", 1)
                    _k = _k.strip()
                    _v = _v.strip().strip("\"'")
                    if _k == "DASHSCOPE_API_KEY":
                        DASHSCOPE_API_KEY = _v
                        break

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


def _encode_image(image_path: str | Path) -> str:
    """Encode image file to base64 data URL."""
    path = Path(image_path)
    if not path.exists():
        raise FileNotFoundError(f"Image not found: {path}")

    ext = path.suffix.lower().lstrip(".")
    mime_map = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png", "webp": "webp"}
    mime = mime_map.get(ext, "jpeg")

    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")

    return f"data:image/{mime};base64,{b64}"


def _call_qwen_vl(
    image_path: str | Path,
    prompt: str,
    temperature: float = 0.3,
) -> str:
    """Call Qwen-VL API and return analysis text."""
    if not DASHSCOPE_API_KEY:
        raise RuntimeError(
            "DASHSCOPE_API_KEY not set. "
            "Get your key at https://dashscope.console.aliyun.com"
        )

    image_data = _encode_image(image_path)

    headers = {
        "Authorization": f"Bearer {DASHSCOPE_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": QWEN_VL_MODEL,
        "input": {
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"image": image_data},
                        {"text": prompt},
                    ],
                }
            ]
        },
        "parameters": {
            "temperature": temperature,
            "max_tokens": 2048,
        },
    }

    resp = requests.post(DASHSCOPE_URL, headers=headers, json=payload, timeout=QWEN_VL_TIMEOUT)
    resp.raise_for_status()
    data = resp.json()

    # Check for API error
    if "output" not in data and "code" in data:
        code = data.get("code", "")
        msg = data.get("message", data.get("msg", ""))
        raise RuntimeError(f"Qwen-VL API error [{code}]: {msg}")

    # Parse DashScope response format
    output = data.get("output", {})
    choices = output.get("choices", [])
    if choices:
        message = choices[0].get("message", {})
        content = message.get("content", "")
        # content may be list or string
        if isinstance(content, list):
            texts = []
            for item in content:
                if isinstance(item, dict) and "text" in item:
                    texts.append(item["text"])
                elif isinstance(item, str):
                    texts.append(item)
            return "\n".join(texts)
        return content

    raise RuntimeError(f"Unexpected API response: {json.dumps(data, ensure_ascii=False)[:500]}")


def _load_prompt(name: str) -> str:
    """Load a prompt template from prompts/ directory."""
    path = PROMPTS_DIR / name
    if not path.exists():
        raise FileNotFoundError(f"Prompt file not found: {path}")
    return path.read_text(encoding="utf-8")


# ── Analysis functions ────────────────────────────────────────────────

def analyze_plan(
    image_path: str | Path,
    building_name: str = "",
    architect: str = "",
    building_type: str = "",
) -> str:
    """Analyze a floor plan image."""
    prompt_template = _load_prompt("vision_analyze.txt")
    user_prompt = prompt_template.format(
        image_type="平面图",
        building_name=building_name or "未知",
        architect=architect or "未知",
        building_type=building_type or "未知",
    )
    system_instruction = "你是一名建筑空间分析专家。请基于提供的平面图图像，进行面向建筑学教学的专业分析。输出结构化的中文分析文本。"

    # Combine system instruction with detailed prompt
    full_prompt = f"{system_instruction}\n\n{user_prompt}"
    return _call_qwen_vl(image_path, full_prompt, temperature=0.3)


def analyze_section(
    image_path: str | Path,
    building_name: str = "",
    architect: str = "",
    building_type: str = "",
) -> str:
    """Analyze a section/elevation image."""
    prompt_template = _load_prompt("vision_analyze.txt")
    user_prompt = prompt_template.format(
        image_type="剖面图",
        building_name=building_name or "未知",
        architect=architect or "未知",
        building_type=building_type or "未知",
    )
    system_instruction = "你是一名建筑空间分析专家。请基于提供的剖面图图像，重点分析空间序列、光路径和结构表达。输出结构化的中文分析文本。"

    full_prompt = f"{system_instruction}\n\n{user_prompt}"
    return _call_qwen_vl(image_path, full_prompt, temperature=0.3)


def analyze_space_photo(
    image_path: str | Path,
    building_name: str = "",
    architect: str = "",
    building_type: str = "",
) -> str:
    """Analyze an interior/exterior space photo."""
    prompt_template = _load_prompt("vision_analyze.txt")
    user_prompt = prompt_template.format(
        image_type="空间照片",
        building_name=building_name or "未知",
        architect=architect or "未知",
        building_type=building_type or "未知",
    )
    system_instruction = "你是一名建筑空间分析专家。请基于提供的空间照片，重点分析空间氛围、光环境品质和材料表现。输出结构化的中文分析文本。"

    full_prompt = f"{system_instruction}\n\n{user_prompt}"
    return _call_qwen_vl(image_path, full_prompt, temperature=0.4)


# ── Pipeline ──────────────────────────────────────────────────────────

def run_vision_pipeline(
    image_dir: str | Path,
    building_name: str = "",
    architect: str = "",
    building_type: str = "",
) -> dict:
    """
    Run visual analysis on all images in a case directory.

    Expected image naming convention:
      plan.* or plan_*.jpg   → analyzed as floor plan
      section.* or section_*.jpg → analyzed as section
      space_*.jpg, photo_*.jpg, interior_*.jpg → analyzed as space photo

    Args:
        image_dir: Directory containing curated images
        building_name: Building name for context
        architect: Architect name for context
        building_type: Building type for context

    Returns:
        dict with plan_analysis, section_analysis, photo_analyses, design_synthesis
    """
    base = Path(image_dir)
    if not base.exists():
        raise FileNotFoundError(f"Image directory not found: {base}")

    images = sorted(base.glob("*"))
    images = [f for f in images if f.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp")]

    if not images:
        raise FileNotFoundError(f"No images found in {base}")

    print(f"  [Vision] Found {len(images)} images in {base.name}")

    result = {
        "building_name": building_name,
        "architect": architect,
        "plan_analysis": "",
        "section_analysis": "",
        "photo_analyses": [],
    }

    for img in images:
        name_lower = img.stem.lower()

        if "plan" in name_lower or "平面" in name_lower:
            print(f"    Analyzing plan: {img.name}")
            result["plan_analysis"] = analyze_plan(
                img, building_name, architect, building_type
            )

        elif "section" in name_lower or "剖面" in name_lower:
            print(f"    Analyzing section: {img.name}")
            result["section_analysis"] = analyze_section(
                img, building_name, architect, building_type
            )

        elif any(kw in name_lower for kw in ("space", "photo", "interior", "exterior", "空间", "室内", "室外")):
            print(f"    Analyzing photo: {img.name}")
            analysis = analyze_space_photo(
                img, building_name, architect, building_type
            )
            result["photo_analyses"].append({
                "image": img.name,
                "analysis": analysis,
            })

        else:
            # Default: treat as space photo
            print(f"    Analyzing (as photo): {img.name}")
            analysis = analyze_space_photo(
                img, building_name, architect, building_type
            )
            result["photo_analyses"].append({
                "image": img.name,
                "analysis": analysis,
            })

    return result


def vision_to_markdown(vision_result: dict) -> str:
    """Convert vision analysis results to Dify-optimized Markdown section."""
    lines = ["## 视觉分析", ""]

    # Plan analysis
    if vision_result.get("plan_analysis"):
        lines.append("### 平面组织分析")
        lines.append("")
        lines.append(vision_result["plan_analysis"])
        lines.append("")

    # Section analysis
    if vision_result.get("section_analysis"):
        lines.append("### 剖面空间分析")
        lines.append("")
        lines.append(vision_result["section_analysis"])
        lines.append("")

    # Photo analyses
    for pa in vision_result.get("photo_analyses", []):
        img_name = pa.get("image", "空间照片")
        lines.append(f"### 空间氛围分析 — {img_name}")
        lines.append("")
        lines.append(pa.get("analysis", ""))
        lines.append("")

    return "\n".join(lines)


# ── CLI ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python vision_analyzer.py <image_dir> [building_name]")
        print("Example: python vision_analyzer.py images/Church_of_the_Light '光之教堂'")
        sys.exit(1)

    img_dir = Path(sys.argv[1])
    bldg_name = sys.argv[2] if len(sys.argv) > 2 else img_dir.name

    if not DASHSCOPE_API_KEY:
        print("[ERROR] DASHSCOPE_API_KEY not set.")
        print("  Get key: https://dashscope.console.aliyun.com")
        print("  Then: export DASHSCOPE_API_KEY=sk-xxxx")
        sys.exit(1)

    result = run_vision_pipeline(img_dir, building_name=bldg_name)
    md = vision_to_markdown(result)
    print("\n" + "=" * 50)
    print(md)
