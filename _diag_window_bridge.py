# -*- coding: utf-8 -*-
"""Visual Context Bridge 诊断脚本：打印 4 层 checkpoint，定位"视觉信息死在那一层"。

用法:
    python _diag_window_bridge.py <图片路径> [--question "你能看到窗户吗"]

4 个 checkpoint:
    ① RAW RESPONSE        Qwen-VL/中转站 原始返回（_call_qwen_vl 的 content）
    ② PARSED RESULT       _validated_analysis 结构化后（visible_facts/inferences/unknowns/dimension_annotations）
    ③ SAVED STATE         前端 selectedFileContexts() 实际传给 chat 的字段（模拟）
    ④ CHAT CONTEXT        _build_visual_reference 生成的 visual_reference + selected_project_files

附加: --probe 用"明确要求列出窗/门编号"的针对性 prompt 再打一次 Qwen，
      用于区分「Qwen 看到但默认摘要没写」 vs 「Qwen 真没看到/图上没有」。
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# 控制台输出容错：GBK 控制台遇到生僻字符会崩，统一用 UTF-8 + replace
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import image_analyzer as ia
from architect_chat import _build_visual_reference, _prepare_file_contexts


def _call_qwen_vl_raw(data: bytes, mime_type: str, user_question: str) -> str:
    """复制 image_analyzer._call_qwen_vl 的请求逻辑，返回原始 content 字符串（不解析）。

    image_analyzer._call_qwen_vl 内部会 _save_raw 原文，但函数返回的是解析后的 dict；
    这里为 checkpoint ① 单独拿原始文本，保证 RAW 层可审计。
    """
    import requests
    import base64
    api_key = ia._load_key()
    if not api_key:
        raise RuntimeError("服务端未配置 DASHSCOPE_API_KEY")
    prompt = ia._build_prompt(user_question)
    data_url = f"data:{mime_type};base64,{base64.b64encode(data).decode('ascii')}"
    qwen_model = ia._load_qwen_model()
    print(f"[Vision Debug] RAW请求 Qwen-VL: model={qwen_model}")
    response = requests.post(
        ia.DASHSCOPE_URL,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": qwen_model,
            "input": {"messages": [{"role": "user", "content": [{"image": data_url}, {"text": prompt}]}]},
            "parameters": {"temperature": 0.1, "max_tokens": 2000},
        }, timeout=120,
    )
    response.raise_for_status()
    raw = response.json()
    choices = raw.get("output", {}).get("choices", [])
    if not choices:
        raise RuntimeError("视觉模型没有返回分析结果")
    content = choices[0].get("message", {}).get("content", "")
    if isinstance(content, list):
        content = "\n".join(item.get("text", "") for item in content if isinstance(item, dict))
    ia._save_raw(str(content), "diag-raw")
    return str(content)

PROBE_PROMPT = (
    "这是一张建筑平面图。请严格逐项回答，只输出JSON：\n"
    "{\n"
    '  "has_windows": true/false,\n'
    '  "window_ids": ["所有窗编号，如 C1/C0915，没有就空数组"],\n'
    '  "window_count": 0,\n'
    '  "door_ids": ["所有门编号，如 M0921，没有就空数组"],\n'
    '  "window_locations": ["窗所在位置描述，如「北侧客厅外墙」"],\n'
    '  "visible_evidence": ["你看到窗的依据，如「外墙有两条平行短线表示窗洞」"]\n'
    "}\n"
    "不要推测，只写图中实际可见的内容。"
)


def _scan_windows(text: str) -> dict:
    """扫描文本里与窗/门相关的证据，返回命中统计。"""
    hits = {
        "窗": len(re.findall(r"窗|窗户|开窗|窗洞|窗台", text)),
        "C编号": len(re.findall(r"\bC\d{3,4}\b|\bC\s?[\-－]?\s?\d", text)),
        "门编号": len(re.findall(r"\bM\d{3,4}\b", text)),
        "window": len(re.findall(r"window|opening", text, re.I)),
    }
    return hits


REPORT_FILE: Path | None = None


def checkpoint(no: int, title: str, obj) -> None:
    text = f"\n{'=' * 70}\n[{no}] {title}\n{'=' * 70}\n"
    text += obj if isinstance(obj, str) else json.dumps(obj, ensure_ascii=False, indent=1)
    print(text)
    if REPORT_FILE is not None:
        with REPORT_FILE.open("a", encoding="utf-8") as f:
            f.write(text + "\n")


def main() -> int:
    global REPORT_FILE
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    probe = "--probe" in sys.argv
    question = ""
    report = None
    for i, a in enumerate(sys.argv):
        if a == "--question" and i + 1 < len(sys.argv):
            question = sys.argv[i + 1]
        if a == "--report" and i + 1 < len(sys.argv):
            report = Path(sys.argv[i + 1])
    if not args:
        print("用法: python _diag_window_bridge.py <图片路径> [--question '问句'] [--probe] [--report <输出.md>]")
        return 1
    if report is not None:
        REPORT_FILE = report
        if REPORT_FILE.exists():
            REPORT_FILE.unlink()
        REPORT_FILE.write_text(f"# Visual Context Bridge 诊断报告\n\n图片: {args[0]}\n问句: {question or '(默认)'}\n", encoding="utf-8")
    img = Path(args[0])
    if not img.exists():
        print(f"图片不存在: {img}")
        return 1
    data = img.read_bytes()
    meta = ia.inspect_image(img.name, data)
    print(f"图片: {img.name}  {meta['width']}x{meta['height']}  {meta['size_bytes']} bytes")

    # ── ① RAW RESPONSE（直接打 Qwen-VL，绕过中转站，保证链路干净）──
    raw_text = _call_qwen_vl_raw(data, meta["mime_type"], question or "请帮我理解这张建筑平面图。")
    checkpoint(1, "① QWEN-VL RAW RESPONSE（原始返回全文）", raw_text)
    print("\nRAW 窗证据扫描:", _scan_windows(raw_text))

    # ── ② PARSED VISION RESULT ──
    parsed = ia._validated_analysis(ia._extract_json_robust(raw_text))
    checkpoint(2, "② PARSED VISION RESULT（_validated_analysis 后）", {
        "image_type": parsed["image_type"],
        "visible_facts": parsed["visible_facts"],
        "building_elements": parsed["building_elements"],
        "inferences": parsed["inferences"],
        "unknowns": parsed["unknowns"],
        "dimension_annotations": parsed["dimension_annotations"],
    })
    print("\nPARSED 窗证据扫描:", _scan_windows(json.dumps(parsed, ensure_ascii=False)))

    # ── ③ SAVED STATE（模拟前端 selectedFileContexts() 实际传给 chat 的字段）──
    saved = {
        "id": "file-diag-1", "filename": img.name, "kind": "image",
        "source": "vision", "status": "reference_only",
        "visible_facts": parsed["visible_facts"],
        "inferences": parsed["inferences"],
        "unknowns": parsed["unknowns"],
    }
    # 注意: 前端 selectedFileContexts() 只传上面 3 个字段，
    # dimension_annotations / numeric_verification 均未传（已知桥断裂点）。
    checkpoint(3, "③ SAVED STATE（前端 selectedFileContexts() 传给 chat 的字段）", {
        "传给 chat 的 keys": list(saved.keys()),
        "未传（已知丢失）": ["dimension_annotations", "numeric_verification"],
        "visible_facts": saved["visible_facts"],
    })

    # ── ④ CHAT CONTEXT（_prepare_file_contexts + _build_visual_reference 后注入 LLM 的内容）──
    prepared = _prepare_file_contexts([saved])
    vis_ref = _build_visual_reference(prepared, question or "你能看到窗户吗？")
    checkpoint(4, "④ CHAT CONTEXT（visual_reference 摘要）", vis_ref or "（未生成 visual_reference——file_contexts 里没有图片或图片无三层结果）")
    print("\nCHAT 窗证据扫描:", _scan_windows(vis_ref or ""))
    print("\nselected_project_files 传给 LLM 的 image keys:",
          list(prepared[0].keys()) if prepared else "空")

    # ── 附加: 针对性窗探测（区分"看到没写" vs "真没看到"）──
    if probe:
        try:
            probe_raw = _call_qwen_vl_raw(data, meta["mime_type"], PROBE_PROMPT)
        except Exception as exc:
            print(f"\n[PROBE] 探测调用失败（不影响前 4 层结论）: {type(exc).__name__}: {str(exc)[:120]}")
            return 0
        checkpoint(5, "⑤ PROBE 针对性窗/门探测（明确要求列编号）", probe_raw)
        print("\nPROBE 窗证据扫描:", _scan_windows(probe_raw))

    return 0


if __name__ == "__main__":
    sys.exit(main())
