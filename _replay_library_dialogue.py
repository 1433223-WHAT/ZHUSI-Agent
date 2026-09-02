"""重放 2026-08-19 社区图书馆真实对话（V1.2 空转治理后），输出问题+回答到 Markdown 文档。

用法：
    python _replay_library_dialogue.py
输出：
    output/replay_20260819_community_library.md
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from architect_chat import chat_turn
from conversation_state import empty_state


DIALOGUE = [
    "像老师一样跟我聊一下社区图书馆怎么设计。",
    "2",
    "你可以帮我设计一下吗",
    "你可以帮我设计一下吗",
    "你会设计吗",
    "我需要你给我一个框架",
    "有区别吗",
    "一半一半",
]


def main() -> None:
    state = empty_state()
    history: list[dict] = []
    lines: list[str] = []
    lines.append("# 筑思 Agent 社区图书馆对话重放（V1.2 空转治理后）")
    lines.append("")
    lines.append(f"- 日期：2026-08-19（修复后真实 DeepSeek 调用）")
    lines.append("- 对话来源：2026-08-19 真实失败对话（学生原话逐字重放）")
    lines.append("- 修复内容：见代码修改记录（翻原则 + 提问模块出口 + boundary_rewrite + Router + v2.4 隔离）")
    lines.append("")
    lines.append("---")
    lines.append("")

    for i, msg in enumerate(DIALOGUE, 1):
        lines.append(f"## 第 {i} 轮")
        lines.append("")
        lines.append(f"**学生：** {msg}")
        lines.append("")
        lines.append("**筑思Agent：**")
        lines.append("")
        try:
            result = chat_turn(msg, history, state, turn_id=i)
            reply = result["reply"]
            state = result["state"]
            history.append({"role": "user", "content": msg})
            history.append({"role": "assistant", "content": reply})
        except Exception as exc:
            reply = f"（本轮调用失败：{type(exc).__name__}: {exc}）"
            history.append({"role": "user", "content": msg})
            history.append({"role": "assistant", "content": reply})
        lines.append(reply.strip())
        lines.append("")
        lines.append("---")
        lines.append("")
        print(f"[{i}/{len(DIALOGUE)}] 学生: {msg[:30]}... -> {reply[:60]}...", flush=True)
        time.sleep(1)

    out = Path(__file__).resolve().parent / "output" / "replay_20260819_community_library.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n已写入: {out}")


if __name__ == "__main__":
    main()
