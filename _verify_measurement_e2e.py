# -*- coding: utf-8 -*-
"""对话级验证：尺寸/比例换算由计算器确定性给出（265000→265m，不心算）。"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
import requests

results = []


def check(name, ok, detail=""):
    results.append((name, ok))
    print(("PASS" if ok else "FAIL"), "-", name, detail)


for q, must, must_not in [
    ("265000mm是多少米", "265", "26.5"),
    ("6000是多少米", "6m", ""),
    ("标注尺寸需不需要乘100", "不需要", "乘100"),
]:
    r = requests.post("http://127.0.0.1:8787/api/architect_chat",
                      json={"message": q, "history": [], "state": {}, "turn_id": 1, "file_contexts": []}, timeout=120)
    reply = r.json().get("reply", "")
    ok = must in reply and (not must_not or must_not not in reply)
    check(f"对话 [{q}]", ok, reply[:100].replace("\n", " "))

fails = [r for r in results if not r[1]]
print("=" * 40, f"{len(results)} 项，失败 {len(fails)}")
raise SystemExit(1 if fails else 0)
