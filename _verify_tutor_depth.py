# -*- coding: utf-8 -*-
"""TS V0.2 深层建筑导师压力测试执行器：真实 LLM 跑 11 场景（每场景 2 轮：输入+攻击）。

   输出：demo/shots/tutor_depth_test.md，供裁判按 5 维评分制打分。
   用法：python _verify_tutor_depth.py
"""
from __future__ import annotations

import base64
import json
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from architect_chat import chat_turn
from conversation_state import empty_state

IMG = Path(r"新建文件夹\微信图片_20260818200451_55_360.jpg")

# 11 场景：name, 第一轮输入, 攻击追问, 是否带图
SCENARIOS = [
    ("场景1 局部执着", "我给你一个一草住宅平面，你帮我看看", "你为什么一直讨论这个问题？这是整张图最大的问题吗？", True),
    ("场景2 分析层级", "这个方案有什么问题？", "你为什么直接进入房间关系？你有没有先看整个建筑组织？", True),
    ("场景3 场地缺失", "我想设计一个教学楼，这是我的草图", "那你觉得怎么设计？", True),
    ("场景4 类型理解", "我想参考光之教堂设计教学楼", "为什么你认为教学楼需要教堂的精神性？你有没有先分析两个建筑类型的差异？", False),
    ("场景5 空间关系", "这个建筑怎么改？", "你说南侧好，那为什么？你的依据是什么？", True),
    ("场景6 阶段判断", "我现在刚开始做方案", "我连体块都没确定，你为什么开始讲材料？", False),
    ("场景7 案例滥用", "我喜欢安藤忠雄", "你为什么先想到形式？我喜欢他的是什么？", False),
    ("场景8 常识滥用", "客厅朝北", "为什么？", False),
    ("场景9 经验幻觉", "这里有一个庭院", "你怎么知道安静？", False),
    ("场景10 真正导师", "这是我的方案，你觉得怎么样？", "", True),
    ("场景11 问题定义权", "我觉得这个方案有问题", "为什么是流线？你怎么判断这是主要问题？", True),
]


def load_image_context() -> dict | None:
    import urllib.request
    try:
        data = IMG.read_bytes()
        body = json.dumps({"filename": "house_plan.jpg", "content_base64": base64.b64encode(data).decode("ascii"), "question": ""}, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request("http://127.0.0.1:8787/api/analyze_image", data=body, headers={"Content-Type": "application/json"})
        img = json.loads(urllib.request.urlopen(req, timeout=150).read().decode("utf-8"))
        return {
            "id": "f1", "filename": "house_plan.jpg", "kind": "image", "source": "vision", "status": "reference_only",
            "visible_facts": img.get("visible_facts", []), "inferences": img.get("inferences", []),
            "unknowns": img.get("unknowns", []), "building_elements": img.get("building_elements", {}),
            "dimension_annotations": img.get("dimension_annotations", []), "numeric_verification": img.get("numeric_verification", {}),
        }
    except Exception as e:
        print(f"⚠️ 图分析失败: {e}")
        return None


def run_turn(message: str, state: dict, fc: list, turn_id: int) -> tuple[dict, dict]:
    r = chat_turn(message, [], state, turn_id=turn_id, file_contexts=fc)
    return r, r["state"]


def main() -> int:
    out = Path("demo/shots/tutor_depth_test.md")
    if out.exists():
        out.unlink()
    img_ctx = load_image_context()
    lines = ["# 筑思 Agent 深层建筑导师压力测试 TS V0.2 · 执行记录（真实 LLM）", ""]

    for i, (name, q1, attack, needs_img) in enumerate(SCENARIOS, 1):
        st = empty_state()
        fc = [img_ctx] if (needs_img and img_ctx) else []
        lines.append(f"## {name}")
        lines.append("")
        # 第一轮
        try:
            r1, st = run_turn(q1, st, fc, 1)
            lines.append(f"**学生**：{q1}")
            lines.append(f"**AI（第一轮）**：{r1['reply'][:600]}")
            lines.append("")
            print(f"[{i:02d}/11] {name} 轮1 完成")
        except Exception as e:
            lines.append(f"**学生**：{q1}\n**AI**：ERROR {str(e)[:100]}\n")
            print(f"[{i:02d}/11] {name} 轮1 失败: {str(e)[:60]}")
            lines.append("")
            continue
        # 攻击追问
        if attack:
            try:
                r2, st = run_turn(attack, st, fc, 2)
                lines.append(f"**学生（攻击）**：{attack}")
                lines.append(f"**AI（第二轮）**：{r2['reply'][:500]}")
                lines.append("")
                print(f"[{i:02d}/11] {name} 轮2 完成")
            except Exception as e:
                lines.append(f"**学生（攻击）**：{attack}\n**AI**：ERROR {str(e)[:100]}\n")
                print(f"[{i:02d}/11] {name} 轮2 失败: {str(e)[:60]}")
        lines.append("---")
        lines.append("")

    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n✅ 执行记录：{out}（11 场景）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
