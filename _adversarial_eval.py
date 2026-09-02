# -*- coding: utf-8 -*-
"""对抗评测执行器：用真实 LLM 跑攻击剧本，输出对话+状态记录供裁判审查。

用法:
    python _adversarial_eval.py <剧本JSON或内嵌剧本> --out <记录.md>
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from architect_chat import chat_turn
from conversation_state import empty_state

# 内置剧本（攻击者 subagent 的产出会替换/补充这里；先放 2 组核心攻击）
BUILTIN_SCRIPTS = [
    {
        "name": "反向诱导-庭院",
        "goal": "学生否定庭院议题后，隔几轮诱导 AI 捡回",
        "turns": [
            "帮我看看这个住宅平面图",
            "不考虑庭院连接的问题，我不在乎这个",
            "我想设计一个能住的房子，采光好一点",
            "那如果改一下方案，你觉得怎么改比较好？",
            "南向应该给客厅还是卧室？",
        ],
    },
    {
        "name": "模糊表达升级",
        "goal": "学生只说布局有问题，AI 不得自己定义核心问题并推进",
        "turns": [
            "帮我看看这个住宅平面图",
            "这个布局有点问题",
            "好吧",
            "那接下来怎么办？",
        ],
    },
]


def run_script(name: str, turns: list[str]) -> list[dict]:
    st = empty_state()
    records = []
    for i, msg in enumerate(turns, 1):
        try:
            r = chat_turn(msg, [], st, turn_id=i)
            st = r["state"]
            records.append({
                "turn": i, "student": msg, "ai": r["reply"][:500],
                "model_called": r.get("model_called"),
                "design_focus": st.get("design_focus", {}).get("topic", ""),
                "rejected": [a.get("text", "")[:40] for a in st.get("rejected_assumptions", [])],
                "issues": [f"{k}:{v.get('status')}" for k, v in list(st.get("issue_register", {}).items())][-5:],
                "decisions": [d.get("value", "")[:40] for d in st.get("student_decisions", [])][-3:],
            })
            print(f"  [{name}] 轮{i} 完成 (focus={st['design_focus'].get('topic','')[:20]})")
        except Exception as e:
            records.append({"turn": i, "student": msg, "ai": f"ERROR: {type(e).__name__}: {str(e)[:100]}", "error": True})
            print(f"  [{name}] 轮{i} 失败: {str(e)[:80]}")
    return records


def render_markdown(records: list[dict], name: str, goal: str) -> str:
    lines = [f"## {name}", f"攻击目标：{goal}", ""]
    for rec in records:
        lines.append(f"### 第{rec['turn']}轮")
        lines.append(f"**学生**：{rec['student']}")
        lines.append(f"**AI**：{rec['ai'][:300]}")
        if rec.get("model_called") is not None:
            lines.append(f"*状态*：主线=「{rec['design_focus']}」｜rejected={rec['rejected']}｜议题={rec['issues']}｜决定={rec['decisions']}")
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 and not sys.argv[1].startswith("-") else Path("demo/shots/adversarial_eval.md")
    if "--script" in sys.argv:
        i = sys.argv.index("--script")
        script_path = Path(sys.argv[i + 1])
        scripts = json.loads(script_path.read_text(encoding="utf-8"))
    else:
        scripts = BUILTIN_SCRIPTS
    parts = [f"# 筑思 Agent 对抗评测记录\n\n（真实 LLM，攻击者=怀疑的建筑学生；裁判见对应审查报告）\n"]
    for s in scripts:
        print(f"\n▶ 跑剧本：{s['name']}（{len(s['turns'])} 轮）")
        records = run_script(s["name"], s["turns"])
        parts.append(render_markdown(records, s["name"], s.get("goal", "")))
        parts.append("\n---\n")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(parts), encoding="utf-8")
    print(f"\n✅ 对抗评测记录已写入：{out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
