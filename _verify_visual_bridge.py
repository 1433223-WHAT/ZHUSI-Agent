# -*- coding: utf-8 -*-
"""Visual Context Bridge 修复验收脚本（Building Elements + 尺寸桥 + 表述边界）。

用法:
    python _verify_visual_bridge.py            # 本地单元验证（不调 API）
    python _verify_visual_bridge.py --live     # + live 端到端（真实 Qwen 分析住宅平面图）

覆盖：
    V1 building_elements 解析契约（四项恒存在；空数组=未检测到）
    V2 _prepare_file_contexts 透传 building_elements/dimension_annotations/numeric_verification
    V3 _build_visual_reference 注入窗/门/楼梯/开口/尺寸标注原文/尺寸识别
    V4 全空要素 → "未检测到"措辞（不得断言不存在）
    V5 visual_boundary_rule 存在（_call_deepseek context 注入）
    V6 (live) 默认 question 上传住宅平面图 → building_elements.windows 非空（不依赖问题诱导）
    V7 (live) chat context 含窗信息（用户问"能看到窗户吗"→ visual_reference 有窗）
"""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

BASE = Path(__file__).resolve().parent
PASS = 0
FAIL = 0
FAILED = []


def check(name: str, cond: bool, detail: str = "") -> None:
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"PASS - {name}")
    else:
        FAIL += 1
        FAILED.append(name)
        print(f"FAIL - {name} {detail}")


# ── 导入被测模块 ──
import image_analyzer as ia  # noqa: E402
from architect_chat import _build_visual_reference, _call_deepseek, _prepare_file_contexts  # noqa: E402


def test_parse_contract() -> None:
    print("\n── V1 building_elements 解析契约 ──")
    r = ia._validated_building_elements({})
    check("V1.1 无字段→四项空数组", set(r.keys()) == {"windows", "doors", "stairs", "openings"} and all(v == [] for v in r.values()), str(r))
    r = ia._validated_building_elements({"building_elements": {"windows": [{"location": "主卧南侧", "count": 1, "confidence": "high"}]}})
    check("V1.2 dict 元素清洗保留", r["windows"] == [{"location": "主卧南侧", "count": "1", "confidence": "high"}], str(r["windows"]))
    r = ia._validated_building_elements({"building_elements": {"windows": ["主卧南侧有窗"], "doors": "bad"}})
    check("V1.3 字符串元素→location dict", r["windows"] == [{"location": "主卧南侧有窗"}], str(r["windows"]))
    check("V1.4 非法子项→空数组", r["doors"] == [], str(r["doors"]))
    r = ia._validated_building_elements({"building_elements": {"windows": [{}], "stairs": []}})
    check("V1.5 空 dict 过滤", r["windows"] == [], str(r["windows"]))


def test_prepare_file_contexts() -> None:
    print("\n── V2 _prepare_file_contexts 透传 ──")
    item = {
        "id": "f1", "filename": "plan.png", "kind": "image", "mime_type": "image/png",
        "visible_facts": ["有轴网"], "inferences": [], "unknowns": [],
        "building_elements": {"windows": [{"location": "客厅北侧", "count": 1}], "doors": [{"id": "M2421"}], "stairs": [], "openings": []},
        "dimension_annotations": ["顶部标注6000"],
        "numeric_verification": {"annotations": [{"text": "6000", "status": "uncertain"}], "conflicts": [], "summary": "ok"},
    }
    out = _prepare_file_contexts([item])[0]
    check("V2.1 building_elements 透传", out.get("building_elements", {}).get("windows") == [{"location": "客厅北侧", "count": 1}], str(out.get("building_elements")))
    check("V2.2 dimension_annotations 透传", out.get("dimension_annotations") == ["顶部标注6000"], str(out.get("dimension_annotations")))
    check("V2.3 numeric_verification 透传", out.get("numeric_verification", {}).get("annotations", [{}])[0].get("text") == "6000", str(out.get("numeric_verification")))
    out2 = _prepare_file_contexts([{"kind": "image", "filename": "a.png"}])[0]
    check("V2.4 缺失字段→空结构", out2.get("building_elements") == {} and out2.get("dimension_annotations") == [], str(out2))


def test_visual_reference() -> None:
    print("\n── V3/V4 _build_visual_reference 注入 ──")
    img = {
        "kind": "image", "filename": "plan.png",
        "visible_facts": ["这是一张住宅平面图"], "inferences": [], "unknowns": ["缺指北针"],
        "building_elements": {
            "windows": [{"location": "老人房南侧墙体", "count": 1, "confidence": "high"}],
            "doors": [{"id": "M2421", "location": "北侧主入口"}],
            "stairs": [{"location": "车库西侧"}],
            "openings": [],
        },
        "dimension_annotations": ["顶部标注6000"],
        "numeric_verification": {"annotations": [{"text": "6000", "status": "uncertain"}], "conflicts": [], "summary": "ok"},
    }
    ref = _build_visual_reference([img], "你能看到窗户吗？")
    check("V3.1 窗注入", "窗：老人房南侧墙体" in ref, ref[:200])
    check("V3.2 门注入", "M2421" in ref, ref[:200])
    check("V3.3 楼梯注入", "楼梯：车库西侧" in ref, ref[:200])
    check("V3.4 尺寸标注原文注入", "尺寸标注原文：顶部标注6000" in ref, ref[:200])
    check("V3.5 尺寸识别注入", "尺寸识别：6000（待核验）" in ref, ref[:200])
    # 全空要素 → "未检测到"措辞
    empty_img = {
        "kind": "image", "filename": "vague.png",
        "visible_facts": ["画面模糊"], "inferences": [], "unknowns": ["无法判断"],
        "building_elements": {"windows": [], "doors": [], "stairs": [], "openings": []},
        "dimension_annotations": [], "numeric_verification": {},
    }
    ref2 = _build_visual_reference([empty_img], "能看到窗户吗？")
    check("V4.1 全空→未检测到措辞", "均未检测到" in ref2 and "不代表图中不存在" in ref2 and "图中没有" not in ref2, ref2[:300])
    # 完全没有 building_elements 字段（旧数据）→ 不崩、无要素行
    legacy = {"kind": "image", "filename": "old.png", "visible_facts": ["老图"], "inferences": [], "unknowns": []}
    ref3 = _build_visual_reference([legacy], "有什么？")
    check("V4.2 旧数据兼容", "建筑要素" not in ref3 and "可见事实：老图" in ref3, ref3[:200])


def test_boundary_rule() -> None:
    print("\n── V5 visual_boundary_rule 注入 ──")
    import inspect
    src = inspect.getsource(_call_deepseek)
    check("V5.1 context 含 visual_boundary_rule", "visual_boundary_rule" in src)
    check("V5.2 规则含'未检测到'", "未检测到" in src and "不存在" in src and "不得断言" in src)


def test_live() -> None:
    print("\n── V6/V7 live 端到端（真实 Qwen 分析）──")
    img = BASE / "新建文件夹" / "微信图片_20260818200451_55_360.jpg"
    if not img.exists():
        check("V6.0 测试图存在", False, str(img))
        return
    data = img.read_bytes()
    meta = ia.inspect_image(img.name, data)
    # 默认 question（空）——不依赖问题诱导
    raw = None
    import base64 as b64
    import requests
    api_key = ia._load_key()
    prompt = ia._build_prompt("")
    data_url = f"data:{meta['mime_type']};base64,{b64.b64encode(data).decode('ascii')}"
    resp = requests.post(
        ia.DASHSCOPE_URL,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={"model": ia._load_qwen_model(),
              "input": {"messages": [{"role": "user", "content": [{"image": data_url}, {"text": prompt}]}]},
              "parameters": {"temperature": 0.1, "max_tokens": 2000}},
        timeout=150,
    )
    resp.raise_for_status()
    raw = resp.json()["output"]["choices"][0]["message"]["content"]
    if isinstance(raw, list):
        raw = "\n".join(x.get("text", "") for x in raw if isinstance(x, dict))
    parsed = ia._validated_analysis(ia._extract_json_robust(str(raw)))
    wins = parsed.get("building_elements", {}).get("windows") or []
    check("V6.1 默认question→windows非空", len(wins) >= 1, f"windows={len(wins)} 内容={json.dumps(wins, ensure_ascii=False)[:200]}")
    check("V6.2 窗位置描述具体", any("墙" in str(w.get("location", "")) for w in wins), json.dumps(wins, ensure_ascii=False)[:200])
    # V7 chat 链路
    file_ctx = [{
        "id": "f-live", "filename": img.name, "kind": "image", "mime_type": "image/jpeg",
        "visible_facts": parsed.get("visible_facts", []), "inferences": parsed.get("inferences", []),
        "unknowns": parsed.get("unknowns", []),
        "building_elements": parsed.get("building_elements", {}),
        "dimension_annotations": parsed.get("dimension_annotations", []),
        "numeric_verification": parsed.get("numeric_verification", {}),
    }]
    ref = _build_visual_reference(_prepare_file_contexts(file_ctx), "你能看到窗户吗？")
    check("V7.1 chat context 含窗行", "建筑要素：窗：" in ref, ref[:400])
    check("V7.2 chat context 含窗位置", any(str(w.get("location", ""))[:10] in ref for w in wins), ref[:400])


def main() -> int:
    test_parse_contract()
    test_prepare_file_contexts()
    test_visual_reference()
    test_boundary_rule()
    if "--live" in sys.argv:
        test_live()
    print(f"\n{'=' * 50}\n结果: {PASS} 通过, {FAIL} 失败")
    if FAILED:
        print("失败项:", FAILED)
        return 1
    print("全部通过 ✅")
    return 0


if __name__ == "__main__":
    sys.exit(main())
