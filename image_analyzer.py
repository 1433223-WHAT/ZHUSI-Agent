"""Validated architectural image inspection and structured visual analysis."""

from __future__ import annotations

import base64
import io
import json
import re
import time
from pathlib import Path

import requests
from PIL import Image, UnidentifiedImageError


BASE = Path(__file__).resolve().parent
MAX_IMAGE_BYTES = 8 * 1024 * 1024
MAX_PIXELS = 25_000_000
SUPPORTED = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}
DASHSCOPE_URL = "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation"


def _load_key() -> str:
    path = BASE / ".env"
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("DASHSCOPE_API_KEY="):
                return line.split("=", 1)[1].split("#", 1)[0].strip().strip('"').strip("'")
    return ""


def _load_qwen_model() -> str:
    """Qwen-VL 模型：默认 qwen-vl-plus，可用 .env QWEN_VL_MODEL 切换为 qwen-vl-max 等。"""
    path = BASE / ".env"
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("QWEN_VL_MODEL="):
                return line.split("=", 1)[1].split("#", 1)[0].strip().strip('"').strip("'")
    return "qwen-vl-plus"


def _load_relay_config() -> dict:
    """读取中转站视觉配置（VISION_RELAY_*）。未配置则 base/key 为空。"""
    cfg = {"base": "", "key": "", "model": "gpt-4o"}
    env_map = {"VISION_RELAY_BASE_URL": "base", "VISION_RELAY_API_KEY": "key", "VISION_RELAY_MODEL": "model"}
    path = BASE / ".env"
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            s = line.strip()
            for env_key, cfg_key in env_map.items():
                if s.startswith(env_key + "="):
                    cfg[cfg_key] = s.split("=", 1)[1].split("#", 1)[0].strip().strip('"').strip("'")
    return cfg


def _build_prompt(question: str) -> str:
    return f"""你是筑思Agent的建筑图像阅读工具。用户的问题是：{question or '请帮助我理解这张建筑相关图片。'}
只分析图片中实际可见的内容，不替学生完成设计，不得根据模糊图像编造尺寸、比例、功能或规范结论。
请只返回JSON对象：
{{
  "image_type": "site_photo|plan|section|elevation|diagram|sketch|rendering|other",
  "visible_facts": ["图片中明确可见、可直接描述的事实（几何/图形为主；提到尺寸时用'检测到标注'措辞，不要自行断定它就是总长/总宽）"],
  "building_elements": {{
    "windows": [{{"location":"窗户所在墙体位置描述，如'主卧南侧外墙'","count":数量,"confidence":"low|medium|high"}}],
    "doors": [{{"id":"门编号如M2421，无编号给'未编号'","location":"门所在位置"}}],
    "stairs": ["楼梯位置描述"],
    "openings": ["洞口/凹口等其他开口位置描述"]
  }},
  "spatial_model": {{
    "rooms": [{{"name":"房间名如客厅/主卧","location":"在图纸中的方位描述，如'北侧中部、⑥-⑦轴'","zone":"public|private|service|transition，不确定给'unknown'"}}],
    "adjacency": ["相邻关系描述，如'客厅与庭院相邻（南侧）'，没有就空数组"],
    "links": ["连通关系描述，如'门M1221连通厨房与餐厅'、'走廊串联卧室区'，没有就空数组"],
    "circulation": ["交通组织描述，如'主入口在北侧，进门经门厅到客厅；楼梯在库房北侧'，没有就空数组"]
  }},
  "inferences": [{{"content":"基于图像作出的推测","basis":"推测依据","confidence":"low|medium|high"}}],
  "unknowns": ["缺少比例尺、图例、方向或清晰度而无法判断的内容"],
  "dimension_annotations": ["图中检测到的所有尺寸/数字标注，只列数字与位置描述（如'左上角标注6000'、'外侧标注265000'），不做任何对象绑定判断"],
  "architecture_questions": ["帮助学生继续思考或补充信息的问题"],
  "warnings": ["图像质量、版权、比例或专业判断限制"]
}}
硬性要求：
一，building_elements 的 windows/doors/stairs/openings 四个子项必须全部输出，不得省略；某类要素图中未检测到时，必须写空数组 []（如 "windows": []），不得用文字省略或用"无"字含糊带过。
二，检测到窗户符号（墙体双线/断开/平行细线）时必须在 windows 中列出位置；不要把窗混入 doors 或只写进 visible_facts 而漏掉 windows。
三，spatial_model 的 rooms/adjacency/links/circulation 四个子项必须全部输出，不得省略；每项只写图中实际可见的关系，不确定就写空数组，不得编造。
四，必须把观察和推测分开。architecture_questions最多3条。dimension_annotations只列数字不做语义判断。"""


def _save_raw(content: str, label: str = "") -> None:
    try:
        log = BASE / "vision_raw.log"
        with log.open("a", encoding="utf-8") as f:
            f.write("\n" + "=" * 60 + f"\n[{label}] {label}\n" + str(content) + "\n")
    except Exception:
        pass


def _post_with_retry(url: str, headers: dict, payload: dict, timeout: int = 150, tries: int = 3) -> requests.Response:
    """带重试的 POST：间歇性 401/5xx 自动重试（中转站限流保护）。"""
    last = None
    for i in range(tries):
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
            if resp.status_code in (200, 400, 404, 422):  # 200 成功；4xx 非认证类直接返回
                return resp
            last = resp
            print(f"[Vision Debug] 中转站返回 {resp.status_code}，重试 {i+1}/{tries-1}")
        except Exception as exc:
            last = exc
            print(f"[Vision Debug] 中转站请求异常({type(exc).__name__})，重试 {i+1}/{tries-1}")
        time.sleep(1 + i)
    if isinstance(last, requests.Response):
        return last
    raise last  # type: ignore[misc]


# 中转站熔断：连续失败后一段时间直接走 Qwen（中转站对频率极敏感）
_relay_failures = 0
_RELAY_CIRCUIT_OPEN_UNTIL = 0.0


def _relay_open() -> bool:
    return time.time() >= _RELAY_CIRCUIT_OPEN_UNTIL


def _relay_fail() -> None:
    global _relay_failures, _RELAY_CIRCUIT_OPEN_UNTIL
    _relay_failures += 1
    if _relay_failures >= 3:
        _RELAY_CIRCUIT_OPEN_UNTIL = time.time() + 600
        print(f"[Vision Debug] 中转站连续失败 {_relay_failures} 次，熔断 10 分钟，直接使用 Qwen-VL")


def _call_relay_vl(data: bytes, mime_type: str, question: str) -> str | None:
    """OpenAI 兼容中转站视觉调用（gpt-5.5 等，Responses API 优先）。未配置/失败返回 None（上层回退 Qwen-VL）。"""
    cfg = _load_relay_config()
    if not cfg.get("key") or not cfg.get("base") or not _relay_open():
        return None
    data_url = f"data:{mime_type};base64,{base64.b64encode(data).decode('ascii')}"
    prompt = _build_prompt(question)
    headers = {"Authorization": f"Bearer {cfg['key']}", "Content-Type": "application/json"}
    print(f"[Vision Debug] Step2 请求中转站: {cfg['base']}, model={cfg.get('model') or 'gpt-5.5'}")
    # 尝试 1：Responses API（/v1/responses，用户配置 wire_api=responses）
    try:
        url = cfg["base"].rstrip("/") + "/v1/responses"
        payload = {
            "model": cfg.get("model") or "gpt-5.5",
            "input": [{"role": "user", "content": [
                {"type": "input_image", "image_url": data_url},
                {"type": "input_text", "text": prompt},
            ]}],
            "temperature": 0.1,
            "max_output_tokens": 3000,
        }
        resp = _post_with_retry(url, headers, payload)
        resp.raise_for_status()
        content = resp.json().get("output_text", "")
        if content:
            _save_raw(str(content), "relay-vision")
            global _relay_failures
            _relay_failures = 0
            return str(content)
    except Exception as exc:
        _relay_fail()
        print(f"[Vision Debug] 中转站 Responses 端点失败({type(exc).__name__}: {str(exc)[:100]})")
    # 尝试 2：Chat Completions（/v1/chat/completions）
    try:
        url = cfg["base"].rstrip("/") + "/v1/chat/completions"
        payload = {
            "model": cfg.get("model") or "gpt-4o",
            "messages": [{"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": data_url}},
                {"type": "text", "text": prompt},
            ]}],
            "temperature": 0.1, "max_tokens": 3000,
        }
        resp = requests.post(url, headers=headers, json=payload, timeout=150)
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        _save_raw(str(content), "relay-vision")
        return str(content)
    except Exception as exc:
        _relay_fail()
        print(f"[Vision Debug] 中转站 Chat 端点失败({type(exc).__name__}: {str(exc)[:100]})，回退 Qwen-VL")
        return None


class ImageAnalysisError(ValueError):
    pass


def inspect_image(filename: str, data: bytes) -> dict:
    safe_name = Path(filename or "").name
    extension = Path(safe_name).suffix.lower()
    if extension not in SUPPORTED:
        raise ImageAnalysisError("仅支持 PNG、JPG、JPEG 和 WEBP 图片。")
    if not data:
        raise ImageAnalysisError("图片内容为空。")
    if len(data) > MAX_IMAGE_BYTES:
        raise ImageAnalysisError("图片超过 8 MB 限制。")
    try:
        with Image.open(io.BytesIO(data)) as image:
            image.verify()
        with Image.open(io.BytesIO(data)) as image:
            width, height = image.size
            actual_format = (image.format or "").upper()
    except (UnidentifiedImageError, OSError) as exc:
        raise ImageAnalysisError("文件扩展名是图片，但内容不是有效图片。") from exc
    expected_formats = {".png": {"PNG"}, ".jpg": {"JPEG"}, ".jpeg": {"JPEG"}, ".webp": {"WEBP"}}
    if actual_format not in expected_formats[extension]:
        raise ImageAnalysisError("图片扩展名与实际格式不一致。")
    if width * height > MAX_PIXELS:
        raise ImageAnalysisError("图片像素超过 2500 万限制，请缩小后重试。")
    return {
        "filename": safe_name, "extension": extension, "mime_type": SUPPORTED[extension],
        "size_bytes": len(data), "width": width, "height": height,
    }


def _call_qwen_vl(data: bytes, mime_type: str, user_question: str) -> dict:
    api_key = _load_key()
    if not api_key:
        raise RuntimeError("服务端未配置 DASHSCOPE_API_KEY")
    prompt = _build_prompt(user_question)
    data_url = f"data:{mime_type};base64,{base64.b64encode(data).decode('ascii')}"
    qwen_model = _load_qwen_model()
    print(f"[Vision Debug] Step1 图片已编码: bytes={len(data)}, mime={mime_type}")
    print(f"[Vision Debug] Step2 请求 Qwen-VL: model={qwen_model}, prompt_len={len(prompt)}")
    try:
        response = requests.post(
            DASHSCOPE_URL,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": qwen_model,
                "input": {"messages": [{"role": "user", "content": [{"image": data_url}, {"text": prompt}]}]},
                "parameters": {"temperature": 0.1, "max_tokens": 3000},
            }, timeout=120,
        )
        response.raise_for_status()
    except Exception as exc:
        print(f"[Vision Debug] Step2 请求失败: {type(exc).__name__}: {exc}")
        raise
    raw = response.json()
    choices = raw.get("output", {}).get("choices", [])
    if not choices:
        print(f"[Vision Debug] Step3 响应无 choices: {str(raw)[:300]}")
        raise RuntimeError("视觉模型没有返回分析结果")
    content = choices[0].get("message", {}).get("content", "")
    if isinstance(content, list):
        content = "\n".join(item.get("text", "") for item in content if isinstance(item, dict))
    print(f"[Vision Debug] Step3 原始响应前200字: {str(content)[:200]}")
    _save_raw(str(content), "qwen-vl")
    parsed = _extract_json_robust(str(content))
    if parsed is None:
        print(f"[Vision Debug] Step4 JSON 解析失败，原始内容: {str(content)[:500]}")
        raise RuntimeError("视觉模型返回的JSON无法解析")
    print(f"[Vision Debug] Step4 JSON 解析成功: keys={list(parsed.keys())}")
    return parsed


def _extract_json_robust(text: str):
    """健壮 JSON 提取：支持纯 JSON / 代码块 / 文字包裹 / 尾随逗号。

    优先尝试完整解析；失败时剥离 markdown 代码块、截取首个平衡花括号、
    容忍尾随逗号后重试。仍失败返回 None（由调用方报错并保留原始内容）。
    """
    text = (text or "").strip()
    if not text:
        return None
    # 1) 直接解析
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # 2) 剥离 markdown 代码块
    m = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1).strip())
        except json.JSONDecodeError:
            pass
    # 3) 提取首个平衡花括号（处理文字包裹/截断）
    start = text.find("{")
    if start != -1:
        depth = 0
        for i in range(start, len(text)):
            ch = text[i]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    candidate = text[start:i + 1]
                    try:
                        return json.loads(candidate)
                    except json.JSONDecodeError:
                        # 4) 容忍尾随逗号（如 {"a":1,}）
                        candidate = re.sub(r",\s*([}\]])", r"\1", candidate)
                        try:
                            return json.loads(candidate)
                        except json.JSONDecodeError:
                            break
        # 5) 花括号未闭合（模型输出被截断）：尝试补全右括号
        candidate = text[start:]
        # 去掉尾部可能的半个 token 残留
        candidate = re.sub(r'[,，]\s*$', '', candidate.rstrip())
        if candidate.endswith('"'):
            candidate += '}'
        else:
            candidate += '}'
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            # 6) 补全后仍失败：逐层剥掉最后一个未闭合的字符串/值再试
            m_tail = re.search(r',\s*"[^"]*"\s*:?\s*$', candidate)
            if m_tail:
                try:
                    return json.loads(candidate[: m_tail.start()] + "}")
                except json.JSONDecodeError:
                    pass
    return None


def _clean_list(value) -> list[str]:
    return [str(item).strip() for item in value if str(item).strip()] if isinstance(value, list) else []


_ELEMENT_KEYS = ("windows", "doors", "stairs", "openings")


def _validated_building_elements(raw: dict) -> dict:
    """解析 building_elements：每个子项必须是数组，元素清洗为 dict；缺失/非法时给空数组。

    契约：windows/doors/stairs/openings 四项永远存在（空数组表示"未检测到"，不代表不存在）。
    """
    be = raw.get("building_elements")
    if not isinstance(be, dict):
        be = {}
    out = {}
    for key in _ELEMENT_KEYS:
        items = be.get(key)
        if not isinstance(items, list):
            out[key] = []
            continue
        cleaned = []
        for item in items:
            if isinstance(item, dict):
                d = {k: str(v).strip() for k, v in item.items() if str(v).strip()}
                if d:
                    cleaned.append(d)
            elif str(item).strip():
                cleaned.append({"location": str(item).strip()})
        out[key] = cleaned
    return out


def _validated_analysis(raw: dict) -> dict:
    allowed_types = {"site_photo", "plan", "section", "elevation", "diagram", "sketch", "rendering", "other"}
    image_type = raw.get("image_type", "other")
    inferences = []
    for item in raw.get("inferences", []) if isinstance(raw.get("inferences"), list) else []:
        if not isinstance(item, dict) or not str(item.get("content", "")).strip():
            continue
        confidence = item.get("confidence", "low")
        inferences.append({
            "content": str(item["content"]).strip(), "basis": str(item.get("basis", "未说明依据")).strip(),
            "confidence": confidence if confidence in {"low", "medium", "high"} else "low",
        })
    unknowns = _clean_list(raw.get("unknowns"))
    if not unknowns:
        unknowns = ["仅凭当前图片无法确认比例、精确尺寸和完整功能关系。"]
    return {
        "image_type": image_type if image_type in allowed_types else "other",
        "visible_facts": _clean_list(raw.get("visible_facts")),
        "building_elements": _validated_building_elements(raw),
        "spatial_model": _validated_spatial_model(raw),
        "inferences": inferences,
        "unknowns": unknowns,
        "dimension_annotations": _clean_list(raw.get("dimension_annotations")),
        "architecture_questions": _clean_list(raw.get("architecture_questions"))[:3],
        "warnings": _clean_list(raw.get("warnings")),
    }


def _validated_spatial_model(raw: dict) -> dict:
    """解析 spatial_model：rooms/adjacency/links/circulation 四项恒存在。

    契约：这是聊天模型做"整体→局部"分析的空间拓扑基础；
    每项只收图面可确认的内容，不清洗为臆测。
    """
    sm = raw.get("spatial_model")
    if not isinstance(sm, dict):
        sm = {}
    rooms = []
    for item in sm.get("rooms") or []:
        if isinstance(item, dict):
            d = {k: str(v).strip() for k, v in item.items() if str(v).strip()}
            if d.get("name"):
                rooms.append(d)
        elif str(item).strip():
            rooms.append({"name": str(item).strip()})
    return {
        "rooms": rooms[:30],
        "adjacency": _clean_list(sm.get("adjacency"))[:20],
        "links": _clean_list(sm.get("links"))[:20],
        "circulation": _clean_list(sm.get("circulation"))[:15],
    }


def analyze_architecture_image(filename: str, data: bytes, question: str = "") -> dict:
    metadata = inspect_image(filename, data)
    # 视觉调用：中转站（OpenAI 兼容）优先 → 失败回退 Qwen-VL
    def _call_vision():
        relay_raw = _call_relay_vl(data, metadata["mime_type"], question)
        if relay_raw is not None:
            return _validated_analysis(_extract_json_robust(relay_raw))
        raise RuntimeError("中转站未配置")
    try:
        try:
            analysis = _call_vision()
        except Exception as relay_exc:
            print(f"[Vision Debug] 中转站视觉失败({type(relay_exc).__name__}: {str(relay_exc)[:120]})，回退 Qwen-VL")
            analysis = _validated_analysis(_call_qwen_vl(data, metadata["mime_type"], question))
    except Exception as exc:
        return {
            **metadata, "status": "failed", "error": str(exc), "image_type": "unknown",
            "visible_facts": [], "building_elements": {k: [] for k in _ELEMENT_KEYS},
            "spatial_model": {"rooms": [], "adjacency": [], "links": [], "circulation": []},
            "inferences": [], "unknowns": [],
            "architecture_questions": [], "warnings": [], "numeric_verification": {"annotations": [], "conflicts": [], "summary": "分析失败"},
        }
    # Numeric Verifier：图纸数值可信性校验（数字不默认 confirmed）+ 绑定验证
    try:
        from numeric_verifier import verify_numeric
        nv = verify_numeric(
            analysis.get("visible_facts") or [],
            dimension_annotations=analysis.get("dimension_annotations") or [],
        )
    except Exception:
        nv = {"annotations": [], "conflicts": [], "summary": "数值校验不可用", "bind_suspects": []}
    return {**metadata, "status": "analyzed", "error": "", **analysis, "numeric_verification": nv}


# ══════════════════════════════════════════════════════════════════
# 跨图联合分析（多楼层/多图）：把两张原图同时给视觉模型，对齐轴网，
# 产出楼层对应关系（stair_matches/voids/terraces/projected_overlaps/uncertain_matches）。
# 用途：用户上传一层+二层时，聊天模型必须基于真实对应关系分析，不再"猜上下层"。
# ══════════════════════════════════════════════════════════════════

_CROSS_LEVEL_PROMPT = """这两张图片是同一栋建筑的两个楼层平面（顺序可能是一层、二层，也可能标注了1F/2F/楼层名，请先识别）。
请先检查两张图的轴网/轮廓/尺寸标注是否属于同一套坐标系，再对齐。只输出JSON，不要输出其他内容：
{
  "cross_level": {
    "floor_identification": "识别出哪张是一层、哪张是二层，依据是什么（如标注/功能/楼梯'上'字）；无法确定就写'无法确定'",
    "grid_aligned": true/false,
    "grid_note": "轴网是否同一套：两张图的轴网编号（如①-⑦ vs ①-⑧）、纵向编号、总尺寸是否一致；不一致必须明确写'两张图轴网/尺寸不一致，无法建立可靠坐标对齐'，并列出具体差异",
    "floor_1_org": "一层空间组织（一句话）：主要功能组、核心空间、交通",
    "floor_2_org": "二层空间组织（一句话）：主要功能组、核心空间、交通",
    "stair_matches": ["上下层楼梯对应关系；无法对应写'无法确定'"],
    "voids": ["一层有、二层无的区域（庭院/挑空/退台）"],
    "terraces": ["可能的露台/退台/悬挑区域及位置"],
    "projected_room_overlaps": ["一层某空间正上方是二层哪个空间，只列出轮廓明显重合、可确认的；必须带 confidence（high/medium/low），如'一层南侧老人房区域上方对应二层主卧区域（confidence: medium，轴网需核对）'"],
    "uncertain_matches": ["所有无法可靠确定的对应关系——必须明确写'无法确定'，绝不编造"]
  }
}
硬性要求：
一，grid_aligned 为 false（轴网/尺寸不一致）时：projected_room_overlaps 只能输出 confidence=low 的条目并全部注明'对齐不可靠'，其余一律进 uncertain_matches；不得输出看似精确的坐标对应。
二，所有对应关系必须基于两张图实际可见的轴网/轮廓/标注；看不清、对不齐、编号不一致就写'无法确定'，绝不猜测或编造。
三，不得输出建筑评价（如'中心错位''空间逻辑不同'），只输出图面关系事实。
四，cross_level 每个子项必须输出，没有就写空数组或'无法确定'。"""


def analyze_cross_level(files: list[dict]) -> dict:
    """多图联合分析：files = [{"filename","data"(bytes),"mime_type"}...]，至少 2 张。

    把全部原图同时发给 Qwen-VL，产出 cross_level（楼层/多图对应关系）。
    失败返回 {"status":"failed","error":...}。
    """
    if len(files) < 2:
        return {"status": "failed", "error": "跨图分析至少需要 2 张图"}
    api_key = _load_key()
    if not api_key:
        return {"status": "failed", "error": "服务端未配置 DASHSCOPE_API_KEY"}
    import base64 as b64
    content = []
    for f in files[:4]:
        data_url = f"data:{f['mime_type']};base64,{b64.b64encode(f['data']).decode('ascii')}"
        content.append({"image": data_url})
    content.append({"text": _CROSS_LEVEL_PROMPT})
    try:
        resp = requests.post(
            DASHSCOPE_URL,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": _load_qwen_model(),
                "input": {"messages": [{"role": "user", "content": content}]},
                "parameters": {"temperature": 0.1, "max_tokens": 3000},
            }, timeout=180,
        )
        resp.raise_for_status()
    except Exception as exc:
        print(f"[Vision Debug] 跨图分析请求失败: {type(exc).__name__}: {str(exc)[:120]}")
        return {"status": "failed", "error": f"跨图分析请求失败: {str(exc)[:120]}"}
    raw = resp.json()
    choices = raw.get("output", {}).get("choices", [])
    if not choices:
        return {"status": "failed", "error": "视觉模型没有返回跨图分析结果"}
    content_text = choices[0].get("message", {}).get("content", "")
    if isinstance(content_text, list):
        content_text = "\n".join(item.get("text", "") for item in content_text if isinstance(item, dict))
    _save_raw(str(content_text), "cross-level")
    parsed = _extract_json_robust(str(content_text))
    if parsed is None or not isinstance(parsed.get("cross_level"), dict):
        return {"status": "failed", "error": "跨图分析结果无法解析", "raw": str(content_text)[:300]}
    return {"status": "analyzed", "cross_level": _validated_cross_level(parsed["cross_level"])}


def _validated_cross_level(cl: dict) -> dict:
    """清洗 cross_level：每个子项恒存在；字符串截断。

    轴网不一致（grid_aligned=false）时：投影对应降级为不确定——宁缺毋错，
    不能拿不可靠的"车库上=书房"喂给聊天模型当事实。
    """
    aligned = str(cl.get("grid_aligned", "")).strip().lower()
    aligned_flag = aligned in ("true", "yes", "是", "一致")
    grid_note = str(cl.get("grid_note", ""))[:300]
    overlaps = _clean_list(cl.get("projected_room_overlaps"))[:10]
    uncertain = _clean_list(cl.get("uncertain_matches"))[:10]
    if not aligned_flag:
        # 轴网不一致：投影对应不可信，全部并入 uncertain（带说明），不保留"确定"语气
        if overlaps:
            uncertain.append("轴网/尺寸不一致，以下投影对应不可靠：" + "；".join(str(x)[:60] for x in overlaps))
        overlaps = []
        if not grid_note:
            grid_note = "两张图轴网/尺寸不一致，无法建立可靠坐标对齐"
    return {
        "floor_identification": str(cl.get("floor_identification", "无法确定"))[:200],
        "grid_aligned": aligned_flag,
        "grid_note": grid_note,
        "floor_1_org": str(cl.get("floor_1_org", ""))[:300],
        "floor_2_org": str(cl.get("floor_2_org", ""))[:300],
        "stair_matches": _clean_list(cl.get("stair_matches"))[:8],
        "voids": _clean_list(cl.get("voids"))[:8],
        "terraces": _clean_list(cl.get("terraces"))[:6],
        "projected_room_overlaps": overlaps,
        "uncertain_matches": uncertain,
    }
