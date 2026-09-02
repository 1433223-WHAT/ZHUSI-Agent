# -*- coding: utf-8 -*-
"""实测 qwen3.7-plus 等候选模型是否可调用。"""
import sys, io, base64
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
import requests

KEY = ""
for line in open(r"E:\AI\项目设计\筑智AI_ArchAI\ArchAI_Builder\.env", encoding="utf-8"):
    if line.strip().startswith("DASHSCOPE_API_KEY="):
        KEY = line.split("=", 1)[1].split("#", 1)[0].strip().strip('"').strip("'")

URL = "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation"
img = open(r"E:\AI\项目设计\筑智AI_ArchAI\ArchAI_Builder\images\Church_of_the_Light\plan.jpg", "rb").read()
du = "data:image/jpeg;base64," + base64.b64encode(img).decode("ascii")

for model in ["qwen3.7-plus", "qwen3.7-vl-plus", "qwen3.7-vl", "qwen3-vl-plus", "qwen-vl-max"]:
    try:
        r = requests.post(URL, headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"},
                          json={"model": model, "input": {"messages": [{"role": "user", "content": [{"image": du}, {"text": "只回复OK"}]}]},
                                "parameters": {"max_tokens": 20}}, timeout=60)
        print(f"{model:<16} {r.status_code}  {'可用' if 'choices' in r.text else r.text[:70].replace(chr(10),' ')}")
    except Exception as exc:
        print(f"{model:<16} 异常 {type(exc).__name__}: {str(exc)[:60]}")
