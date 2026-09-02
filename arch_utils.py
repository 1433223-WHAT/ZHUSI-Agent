# -*- coding: utf-8 -*-
"""arch_utils.py — 建筑基础计算器（Architecture Utility）

确定性计算：单位转换 / 比例换算 / 面积 / 长宽比 / 尺寸链求和 / 比例尺换算。
**不交给 LLM 心算**——265000mm = 265m 这类由代码直接算，杜绝 26.5m 之类错误。

同时承载"建筑制图与图纸阅读"的第一批专业规则（A 章）。
"""

from __future__ import annotations

import re

# ── 单位转换 ─────────────────────────────────────────────

def mm_to_m(mm: float) -> float:
    return mm / 1000.0


def m_to_mm(m: float) -> float:
    return m * 1000.0


def cm_to_mm(cm: float) -> float:
    return cm * 10.0


def fmt_length(mm: float) -> str:
    """智能格式化：>=1000mm 显示 m，否则显示 mm。"""
    if mm >= 1000:
        v = mm / 1000.0
        return f"{v:g}m" if v == int(v) else f"{v:.2f}m"
    return f"{mm:g}mm"


def parse_length(text: str) -> float | None:
    """从文本提取长度并统一到 mm。返回 None 表示无法解析。"""
    m = re.search(r"(\d[\d,，.]*)\s*(mm|毫米|cm|厘米|公分|米|m)?", text)
    if not m:
        return None
    try:
        v = float(m.group(1).replace(",", "").replace("，", ""))
    except ValueError:
        return None
    unit = (m.group(2) or "").strip()
    if unit in ("m", "米"):
        return v * 1000
    if unit in ("cm", "厘米", "公分"):
        return v * 10
    return v  # mm 或裸值


# ── 比例尺换算（仅用于图面几何长度 ↔ 实际；不缩放已标注尺寸）──

def scale_drawing_to_actual(drawing_mm: float, scale_denominator: float) -> float:
    """图面 mm × 比例分母 = 实际 mm（如 1:100 图面 10mm = 实际 1000mm）。"""
    return drawing_mm * scale_denominator


def scale_actual_to_drawing(actual_mm: float, scale_denominator: float) -> float:
    return actual_mm / scale_denominator


def scale_rule_text(scale_text: str = "1:100") -> str:
    """制图规则（A 章核心）：标注尺寸与比例尺的关系。"""
    return (
        "制图规则：图纸上已标注的尺寸数字按其标注单位表示实际尺寸（6000mm=6m），"
        "不因图纸比例尺而缩放；比例尺（如 1:100）仅用于换算「图上未标注、需从图面几何长度测量」的部分"
        "（图面 1mm = 实际 100mm @1:100）。标注尺寸与图面测量不要混算。"
    )


# ── 几何与面积 ───────────────────────────────────────────

def area_m2(w_mm: float, h_mm: float) -> float:
    return (w_mm * h_mm) / 1_000_000.0


def aspect_ratio(a_mm: float, b_mm: float) -> float:
    if min(a_mm, b_mm) <= 0:
        return 0.0
    return max(a_mm, b_mm) / min(a_mm, b_mm)


def chain_sum(values_mm: list[float]) -> float:
    return sum(values_mm)


# ── 7 题验收（V0.1）──────────────────────────────────────

def verify_seven(question: str) -> str:
    """对尺寸/比例类问句给出确定性回答（供拦截注入）。"""
    q = question
    lines = []
    if re.search(r"1:\d+", q) and re.search(r"比例|是什么意思", q):
        m = re.search(r"1:(\d+)", q)
        lines.append(f"1:{m.group(1)} 是图纸比例尺：图面 1 单位 = 实际 {m.group(1)} 单位。{scale_rule_text()}")
    # 含数字的换算问句
    for num in re.findall(r"(\d[\d,，.]*)\s*(mm|毫米|m|米)?", q):
        raw, unit = num
        if not raw:
            continue
        try:
            v = float(raw.replace(",", ""))
        except ValueError:
            continue
        u = unit.strip()
        if u in ("m", "米"):
            lines.append(f"{raw} = {m_to_mm(v):g}mm")
        elif u in ("mm", "毫米"):
            lines.append(f"{raw}mm = {fmt_length(v)}（{fmt_length(v)}，如按毫米读 {v:g}mm）")
        elif u == "" and v >= 1000:
            lines.append(f"{raw}mm = {fmt_length(v)}")
    if "乘" in q and ("比例" in q or "100" in q):
        lines.append("标注尺寸不需要乘比例：标注数字已表示实际尺寸（6000mm=6m）；比例只用于图面测量换算。")
    if "总尺寸" in q or "哪个数字" in q:
        lines.append("总尺寸判断需绑定验证：仅凭数字大小不能确认哪个是总尺寸；需结合尺寸线位置/覆盖范围/分段链。未绑定前不得叫'总长/总宽'。")
    if "总长" in q or "总宽" in q or "绑定" in q or "对应对象" in q:
        lines.append("数值未绑定到具体对象（总长/开间/层高/墙厚）前，不得使用'总长/总宽/进深'等对象语义；绑定需结合尺寸线位置/覆盖范围/分段链验证。")
    return "\n".join(lines) if lines else ""
