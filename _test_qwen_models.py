# -*- coding: utf-8 -*-
"""实测 DashScope 接受的 Qwen-VL 模型名（不存在会报错）。"""
import sys, io, base64
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
import requests

KEY = ""
path = r"E:\AI\项目设计\筑智AI_ArchAI\ArchAI_Builder\.env"
for line in open(path, encoding="utf-8"):
    if line.strip().startswith("DASHSCOPE_API_KEY="):
        KEY = line.split("=", 1)[1].split("#", 1)[0].strip().strip('"').strip("'")

URL = "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation"
img = open(r"E:\AI\项目设计\筑智AI_ArchAI\ArchAI_Builder\images\Church_of_the_Light\plan.jpg", "rb").read()
du = "data:image/jpeg;base64," + base64.b64encode(img).decode("ascii")

candidates = ["qwen-vl-max", "qwen-vl-plus", "qwen-vl-plus-latest", "qwen-vl-max-latest",
              "qwen2.5-vl-max", "qwen2.5-vl-plus", "qwen3-vl-plus", "qwen3-vl-max", "qwen3-vl-72b-instruct"]

for model in candidates:
    try:
        r = requests.post(URL, headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"},
                          json={"model": model, "input": {"messages": [{"role": "user", "content": [{"image": du}, {"text": "只回复OK"}]}]},
                                "parameters": {"max_tokens": 20}}, timeout=60)
        ok = "choices" in r.text
        print(f"{model:<22} {r.status_code}  {'✅ 可用' if ok else r.text[:80].replace(chr(10),' ')}")
    except Exception as exc:
        print(f"{model:<22} 异常 {type(exc).__name__}: {str(exc)[:60]}")
