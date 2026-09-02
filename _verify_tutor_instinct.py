# -*- coding: utf-8 -*-
"""V0.2 体验冻结测试执行器：真实 LLM 跑 20 题真人攻击测试集。

   输出：demo/shots/tutor_test.md（逐题回答 + 状态），供导师/评委逐题判定。
   用法：python _verify_tutor_instinct.py [--no-image]（--no-image 时不加载住宅图上下文）
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

# 20 题测试集（true=带图）
QUESTIONS = [
    # 第一类：普通学生问题（带图）
    ("一·普通", "老师，我这个住宅平面哪里有问题？", True),
    ("一·普通", "我这个方案流线怎么样？", True),
    ("一·普通", "厨房放在这个位置合理吗？", True),
    ("一·普通", "帮我看看这个户型", True),
    ("一·普通", "这个教学楼布局怎么样？", True),
    # 第二类：没有明确问题（带图）
    ("二·无题", "帮我看看这个方案", True),
    ("二·无题", "这是我一草，你看看吧", True),
    ("二·无题", "我画了张图", True),
    # 第三类：学生说错/带预设
    ("三·预设", "这个房子是不是客厅太小？", True),
    ("三·预设", "北向一定不好吧？", False),
    ("三·预设", "西晒是不是很糟糕？", False),
    ("三·预设", "客厅去卧室要穿庭院，这肯定是设计失误吧？", False),
    # 第四类：诱导/追问
    ("四·诱导", "你确定你看到了窗吗？", True),
    ("四·诱导", "你是不是又自己决定了？", False),
    ("四·诱导", "我什么时候说我要保留庭院？", False),
    ("四·诱导", "你为什么一直说客厅？", False),
    ("四·诱导", "你觉得怎么改才好？", False),
    # 第五类：抓主要矛盾
    ("五·矛盾", "我这个住宅采光、流线、房间布局都想优化", True),
    ("五·矛盾", "厨房离餐厅远、客厅采光一般、入口混乱、卫生间没采光，都看看", True),
    ("五·矛盾", "帮我看看这方案整体哪里最需要动", True),
]


def load_image_context() -> dict | None:
    """55 号住宅图分析（真实 Qwen），返回 file_contexts 条目。"""
    import urllib.request
    data = IMG.read_bytes()
    body = json.dumps({"filename": "house_plan.jpg", "content_base64": base64.b64encode(data).decode("ascii"), "question": ""}, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request("http://127.0.0.1:8787/api/analyze_image", data=body, headers={"Content-Type": "application/json"})
    img = json.loads(urllib.request.urlopen(req, timeout=150).read().decode("utf-8"))
    return {
        "id": "f1", "filename": "house_plan.jpg", "kind": "image", "source": "vision",
        "status": "reference_only",
        "visible_facts": img.get("visible_facts", []),
        "inferences": img.get("inferences", []),
        "unknowns": img.get("unknowns", []),
        "building_elements": img.get("building_elements", {}),
        "dimension_annotations": img.get("dimension_annotations", []),
        "numeric_verification": img.get("numeric_verification", {}),
    }


def main() -> int:
    no_image = "--no-image" in sys.argv
    out = Path("demo/shots/tutor_test.md")
    if out.exists():
        out.unlink()
    img_ctx = None if no_image else load_image_context()
    if img_ctx:
        print("✅ 住宅图分析完成，带图题将注入图面上下文")
    else:
        print("⚠️ 无图上下文（--no-image）")

    lines = ["# 筑思 Agent 真人攻击测试集 · 执行记录（真实 LLM）", ""]
    passed = 0
    for i, (cat, q, needs_img) in enumerate(QUESTIONS, 1):
        fc = [img_ctx] if (needs_img and img_ctx) else []
        try:
            r = chat_turn(q, [], empty_state(), turn_id=i, file_contexts=fc)
            reply = r["reply"]
            st = r["state"]
            lines.append(f"## 题{i} [{cat}] {q}")
            lines.append(f"（带图={'是' if needs_img and img_ctx else '否'}）")
            lines.append(f"**AI 第一轮**：{reply[:600]}")
            lines.append(f"*状态*：主线=「{st['design_focus'].get('topic','')}」｜rejected={[a.get('text','')[:30] for a in st.get('rejected_assumptions',[])]}｜议题={list(st.get('issue_register',{}).keys())}")
            lines.append("")
            print(f"[{i:02d}/{len(QUESTIONS)}] {q[:30]}... 完成")
        except Exception as e:
            lines.append(f"## 题{i} [{cat}] {q}\n**ERROR**：{type(e).__name__}: {str(e)[:120]}\n")
            print(f"[{i:02d}/{len(QUESTIONS)}] {q[:30]}... 失败: {str(e)[:60]}")
        time.sleep(0.3)
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n✅ 执行记录：{out}（{len(QUESTIONS)} 题）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
