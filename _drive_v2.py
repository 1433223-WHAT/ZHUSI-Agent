"""学生驱动脚本 v2：每轮传学生消息，维护 state/history，返回 AI 回复。"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from architect_chat import chat_turn
from conversation_state import empty_state

BASE = Path(__file__).resolve().parent
STATE_FILE = BASE / "_drive_v2_state.json"
HIST_FILE = BASE / "_drive_v2_history.json"
LOG_FILE = BASE / "output" / "student_drive_session.md"


def load():
    state = empty_state()
    history: list[dict] = []
    if STATE_FILE.exists():
        try:
            state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    if HIST_FILE.exists():
        try:
            history = json.loads(HIST_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return state, history


def save(state, history):
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
    HIST_FILE.write_text(json.dumps(history, ensure_ascii=False), encoding="utf-8")


def log(lines: list[str]):
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    if LOG_FILE.exists():
        old = LOG_FILE.read_text(encoding="utf-8")
        LOG_FILE.write_text(old + "\n".join(lines) + "\n", encoding="utf-8")
    else:
        LOG_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")


def reset():
    for f in (STATE_FILE, HIST_FILE):
        if f.exists():
            f.unlink()
    if LOG_FILE.exists():
        LOG_FILE.unlink()
    print("会话已重置")


def main():
    args = sys.argv[1:]
    if args and args[0] == "--reset":
        reset()
        return
    msg = " ".join(args) if args else ""
    if not msg:
        print("用法: python _student_drive.py \"学生消息\"  |  python _student_drive.py --reset")
        return
    state, history = load()
    turn_id = len(history) // 2 + 1
    try:
        r = chat_turn(msg, history, state, turn_id=turn_id)
        reply = r["reply"]
        state = r["state"]
    except Exception as exc:
        reply = f"（调用失败：{type(exc).__name__}: {exc}）"
    history.append({"role": "user", "content": msg})
    history.append({"role": "assistant", "content": reply})
    save(state, history)
    log([
        f"## 第 {turn_id} 轮",
        "",
        f"**学生：** {msg}",
        "",
        f"**筑思Agent：**",
        "",
        reply.strip(),
        "",
        "---",
        "",
    ])
    try:
        print(reply)
    except Exception:
        print("(reply written to log; console encoding issue)")
    time.sleep(0.5)


if __name__ == "__main__":
    main()
