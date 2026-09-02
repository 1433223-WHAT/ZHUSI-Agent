"""验证"可画动作"定义翻掉后的行为：AI 是否先承担设计劳动，再让学生画图检验。

场景：学生持续"都行/你先来"（把推演交给 AI），观察 AI 是否
  - 不再说"你画三个圆试试"（产出外包）
  - 而是"我先把 X 这样组织……你可以画出来看这个关系是否接受"（先设计、再检验）
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from architect_chat import chat_turn
from conversation_state import empty_state


def main() -> None:
    turns = [
        "我是建筑学学生，刚开始做一个社区文化中心的设计。一草阶段，什么都没定，也没画图。老师只给了个大概任务。我现在不知道从哪开始，你跟我一起做一下吧。",
        "都可以吧，你先帮我想想。",
        "都可以吧，你先帮我想想。",
        "都可以吧，你先帮我想想。",
    ]
    state = empty_state()
    history: list[dict] = []
    lines: list[str] = []
    lines.append("# 验证：可画动作定义翻掉（先设计、再检验）")
    lines.append("")
    for i, msg in enumerate(turns, 1):
        lines.append(f"## 第 {i} 轮")
        lines.append(f"**学生：** {msg}")
        lines.append("")
        try:
            r = chat_turn(msg, history, state, turn_id=i)
            reply = r["reply"]
            state = r["state"]
            history.append({"role": "user", "content": msg})
            history.append({"role": "assistant", "content": reply})
        except Exception as exc:
            reply = f"（调用失败：{type(exc).__name__}: {exc}）"
        lines.append(reply.strip())
        lines.append("")
        print(f"[{i}] -> {reply[:60]}...", flush=True)
        time.sleep(1)
    out = Path(__file__).resolve().parent / "output" / "verify_draw_action_20260819.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n已写入: {out}")


if __name__ == "__main__":
    main()
