# -*- coding: utf-8 -*-
"""numeric_verifier.py — 图纸数值可信性校验（Numeric Verifier）

输入边界下一层：视觉模型读到的数字 ≠ 图纸明确存在的事实。
所有数字默认 machine_read（机器读取·待核验）；通过校验才 confirmed；
发现矛盾 → conflicting（不进项目事实）。

校验机制：
  ① 尺寸链校验：分段尺寸之和 vs 总尺寸（矛盾 → 总尺寸 conflicting）
  ② 几何比例弱校验：长×宽比例 vs 图形几何描述（明显矛盾 → 冲突提示，只检测不反推）
"""

from __future__ import annotations

import re

# 数值单位 → mm 换算
_UNIT_TO_MM = {"m": 1000.0, "米": 1000.0, "cm": 10.0, "厘米": 10.0, "公分": 10.0, "mm": 1.0}
_UNIT_AREA = {"㎡", "平方米", "平米", "m²"}
_KIND_KEYWORDS = [
    ("总长度", "total_length"), ("总宽度", "total_width"), ("总尺寸", "total"),
    ("总长", "total_length"), ("总宽", "total_width"), ("长", "length"), ("宽", "width"),
    ("层高", "floor_height"), ("标高", "level"), ("面积", "area"), ("进深", "depth"),
    ("比例", "scale"), ("比例尺", "scale"),
]
_GEOMETRY_HINTS = {
    "横向": "wide", "长条": "wide", "扁长": "wide", "扁宽": "wide", "宽扁": "wide",
    "竖向": "tall", "高耸": "tall", "狭长": "tall", "长向": "wide",
}


def _num(s: str) -> float | None:
    m = re.search(r"(\d[\d,，.]*)", s)
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", "").replace("，", ""))
    except ValueError:
        return None


def _to_mm(value: float, unit: str) -> float:
    return value * _UNIT_TO_MM.get(unit, 1.0)


def _parse_value(text: str) -> tuple[float, str] | None:
    """提取 (数值, 单位)。返回 mm 值 + 原始单位（area 时 unit='area'）。"""
    m = re.search(r"(\d[\d,，.]*)\s*([㎡平方米平米m²]|mm|米|cm|厘米|公分|m)?", text)
    if not m:
        return None
    value = _num(m.group(1))
    if value is None:
        return None
    unit = (m.group(2) or "").strip()
    return value, unit


def _classify(text: str) -> str:
    for kw, kind in _KIND_KEYWORDS:
        if kw in text:
            return kind
    return "dimension"


def extract_numeric_annotations(visible_facts: list[str]) -> list[dict]:
    """从可见事实文本抽数字条目，默认状态 machine_read。"""
    anns = []
    for text in visible_facts:
        if not any(ch in text for ch in "0123456789"):
            continue
        if not any(k in text for k in ("总长", "总宽", "总尺寸", "总长度", "总宽度", "长", "宽", "高", "层高",
                                       "标高", "面积", "比例", "进深", "×", "x", "X", "米", "mm", "M", "+", "、", "，")):
            continue
        kind = _classify(text)
        # 长×宽 对
        pair = re.search(r"([\d,，.]+)\s*(mm|米|m|cm|厘米|公分)?\s*[×xX*]\s*([\d,，.]+)\s*(mm|米|m|cm|厘米|公分)?", text)
        if pair:
            a1 = _num(pair.group(1)); a2 = _num(pair.group(3))
            if a1 is not None and a2 is not None:
                anns.append({
                    "text": text.strip()[:120], "kind": "dimension_pair",
                    "value_mm": [_to_mm(a1, pair.group(2) or ""), _to_mm(a2, pair.group(4) or "")],
                    "status": "machine_read",
                })
                continue
        v = _parse_value(text)
        if v is None:
            continue
        value, unit = v
        # 总尺寸行（含"总…长/宽/全长"等）：单独提取总尺寸值 + 行内其他数为分段
        total_m = re.search(r"总[^0-9]{0,10}(?:长|宽|长度|宽度|尺寸|全长)[^0-9]{0,8}(\d[\d,，.]*)", text)
        if total_m and ("总" in text):
            tval = _num(total_m.group(1))
            if tval is not None:
                other = [n for n in (_num(x) for x in re.findall(r"(\d[\d,，.]*)", text)) if n is not None and abs(n - tval) > 1e-6]
                anns.append({
                    "text": text.strip()[:120], "kind": "total_length" if "长" in text else "total_width",
                    "value_mm": _to_mm(tval, ""), "status": "machine_read",
                })
                if len(other) >= 2:
                    anns.append({
                        "text": text.strip()[:120], "kind": "chain_values",
                        "values_mm": [_to_mm(n, "") for n in other], "status": "machine_read",
                        "chain_ok": True,
                    })
                continue
        # 分段/多值行（仅"分段/之和/分尺寸"语义才作为尺寸链，避免把不同层级数字混加）
        all_nums = [_num(x) for x in re.findall(r"(\d[\d,，.]*)", text)]
        nums = [n for n in all_nums if n is not None]
        if len(nums) >= 2 and kind == "dimension" and "总" not in text and re.search(r"分段|之和|分尺寸|尺寸链", text):
            anns.append({
                "text": text.strip()[:120], "kind": "chain_values",
                "values_mm": [_to_mm(n, "") for n in nums], "status": "machine_read", "chain_ok": True,
            })
            continue
        anns.append({
            "text": text.strip()[:120], "kind": kind,
            "value_mm": _to_mm(value, unit) if unit != "area" else None,
            "value_area": value if unit == "area" else None,
            "status": "machine_read",
        })
    return anns


def _chain_check(anns: list[dict]) -> None:
    """尺寸链校验：仅当「单条总尺寸 + 单条完整尺寸链」时配对校验。

    多条 total 或多条链（横向+纵向并存）无法可靠配对 → 不自动计算，宁缺毋错。
    """
    totals = [a for a in anns if a["kind"] in ("total_length", "total_width", "total") and a.get("value_mm")]
    chains = [a for a in anns if a["kind"] == "chain_values" and a.get("values_mm") and a.get("chain_ok")]
    if len(totals) == 1 and len(chains) == 1:
        t = totals[0]["value_mm"]
        s = sum(chains[0]["values_mm"])
        if abs(s - t) > max(50.0, t * 0.02):  # 2% 容差
            totals[0]["status"] = "conflicting"
            totals[0]["conflict_note"] = f"分段尺寸之和（{s/1000:.3f}m）与总尺寸（{t/1000:.3f}m）不一致"
        else:
            totals[0]["status"] = "confirmed"
    # 其余情况：不配对校验（横向+纵向并存等），保持 machine_read→uncertain


def _geometry_check(anns: list[dict], visible_facts: list[str]) -> list[str]:
    """几何比例弱校验：识别长宽 vs 图形几何描述。只做冲突检测，不反推。"""
    conflicts = []
    pair = next((a for a in anns if a["kind"] == "dimension_pair" and a.get("value_mm")), None)
    if pair:
        a, b = pair["value_mm"]  # a=第一个数（长），b=第二个数（宽）
        wide_hint = any(_GEOMETRY_HINTS.get(k) == "wide" for k in _GEOMETRY_HINTS if k in " ".join(visible_facts))
        if wide_hint and a > 0 and b > 0 and a < b * 0.8:
            conflicts.append(
                f"识别长度（{display_mm(a)}）明显小于识别宽度（{display_mm(b)}），"
                "与'横向长条'的几何描述矛盾，建议复核尺寸"
            )
    return conflicts


def _binding_check(visible_facts: list[str], dimension_annotations: list[str]) -> list[dict]:
    """标注-对象关系误绑定验证（Dimension Semantic Binding）。

    模型可能把局部尺寸（6000）错误绑定为总尺寸。收集"数字清单"，
    对 visible_facts 中"总长/总宽=Y"的断言：若清单中存在明显更大的标注，
    则该绑定可疑（bind_suspect）——不采信，待验证。
    """
    raw_nums = []
    for d in (dimension_annotations or []):
        for x in re.findall(r"(\d[\d,，.]*)", str(d)):
            n = _num(x)
            if n:
                raw_nums.append(n)
    suspects = []
    for text in visible_facts:
        m = re.search(r"总(?:长|宽|尺寸|长度|宽度)[^0-9]{0,8}([\d,，.]+)", text)
        if not m:
            continue
        v = _num(m.group(1))
        if v is None:
            continue
        bigger = sorted({n for n in raw_nums if n > v * 1.5})
        if bigger:
            suspects.append({
                "text": text.strip()[:80],
                "bind_value": v,
                "bigger_values": bigger[:5],
            })
    return suspects


def verify_numeric(visible_facts: list[str], dimension_annotations: list[str] | None = None, geometry_text: str = "") -> dict:
    """入口：对可见事实 + 尺寸标注清单做数字校验 + 语义绑定验证。

    尺寸来源三分类（宁缺毋错）：
      - explicit_total：图纸明确标注的总尺寸（外侧/总长/总宽/全长）→ 最高优先
      - derived：仅当模型在同一行明确给出完整尺寸链（"分段：3600、4200…"）+ 总尺寸时才校验
      - unknown：无明确总尺寸 → 不求和，明示"不足以安全计算"
    绝不把不同位置/层级/尺寸线的数字混加。
    返回 {annotations, conflicts, bind_suspects, note, summary}。
    """
    anns = extract_numeric_annotations(visible_facts)
    # 把模型单独列出的尺寸标注清单并入展示——它们是尺寸数字的主要来源
    for d in (dimension_annotations or []):
        v = _parse_value(str(d))
        if v is None:
            continue
        value, unit = v
        txt = str(d).strip()
        kind = "explicit_total" if any(k in txt for k in ("外侧", "总长", "总宽", "全长", "总尺寸")) else "annotation"
        anns.append({
            "text": txt[:80], "kind": kind,
            "value_mm": _to_mm(value, unit) if unit != "area" else None,
            "value_area": value if unit == "area" else None,
            "status": "machine_read",
        })
    if not anns and not dimension_annotations:
        return {"annotations": [], "conflicts": [], "bind_suspects": [], "note": "", "summary": "未识别到明确的尺寸/数字标注。"}
    # 仅当模型在同一行给出完整尺寸链 + 总尺寸时做链校验（不是全量求和）
    _chain_check(anns)
    geometry_conflicts = _geometry_check(anns, [geometry_text] + visible_facts)
    bind_suspects = _binding_check(visible_facts, dimension_annotations)
    # 其余保持 machine_read 的，显示为待核验
    for a in anns:
        if a["status"] == "machine_read":
            a["status"] = "uncertain"
    # 宁缺毋错：无任何总尺寸信息（明确标注或模型声称）→ 不求和，明示无法安全计算
    has_total = any(a["kind"] in ("explicit_total", "total_length", "total_width", "total") for a in anns)
    note = ""
    if not has_total:
        note = ("未可靠读到明确总尺寸（如外侧/总长/总宽标注）。已有分段数字未求和——"
                "它们可能分属不同尺寸线、方向或层级，不足以安全计算总宽/总长。"
                "如你确认某个方向的总尺寸，可直接告诉我，或补充该方向的外侧标注。")
    summary = "、".join(f"{a['text'][:18]}({a['status']})" for a in anns[:6])
    return {"annotations": anns, "conflicts": geometry_conflicts, "bind_suspects": bind_suspects,
            "note": note, "summary": summary}


def display_mm(value_mm: float) -> str:
    if value_mm >= 1000:
        return f"{value_mm/1000:g}m"
    return f"{value_mm:g}mm"
