# -*- coding: utf-8 -*-
"""视觉模型 5 轮稳定性 Benchmark：qwen-vl-max vs qwen3-vl-plus vs qwen3.7-plus。
合成图（横向总宽14000=6000+8000，纵向总长14000=4500+3500+6000，干扰1200/墙厚200）。
指标：14000/6000/1200 识别、6000判局部、虚构尺寸、错误求和。"""
import sys, io, base64, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
import requests

KEY = ""
for line in open(r"E:\AI\项目设计\筑智AI_ArchAI\ArchAI_Builder\.env", encoding="utf-8"):
    if line.strip().startswith("DASHSCOPE_API_KEY="):
        KEY = line.split("=", 1)[1].split("#", 1)[0].strip().strip('"').strip("'")

URL = "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation"
img = open(r"E:\AI\项目设计\筑智AI_ArchAI\ArchAI_Builder\_test_dims.png", "rb").read()
du = "data:image/png;base64," + base64.b64encode(img).decode("ascii")

PROMPT = """只根据图中明确可见内容回答。
横向最外层总尺寸是多少？
纵向最外层总尺寸是多少？
是否看到 14000、6000、1200？
6000 是总尺寸还是局部分段尺寸？不能确定就写不确定。
图中是否能明确识别窗户？
不要根据住宅常见尺度猜测，不要把未确认数字相加补全总尺寸。"""

KNOWN = {6000, 8000, 14000, 4500, 3500, 6000, 1200, 200, 2500, 1500, 500, 3000, 1000, 2000}


def parse(text):
    r = {"14000": False, "6000": False, "1200": False, "6000_local": False, "window": False, "halluc": [], "sum_error": False}
    r["14000"] = "14000" in text
    r["6000"] = "6000" in text
    r["1200"] = "1200" in text
    r["6000_local"] = "6000" in text and any(w in text for w in ("局部", "分段", "左段", "不是总", "不是整体", "分尺寸"))
    r["window"] = any(w in text for w in ("窗户", "窗"))
    # 虚构尺寸：出现的大数字不在已知集
    for n in re.findall(r"\b(\d{3,6})\b", text):
        v = int(n)
        if v not in KNOWN and v > 200:
            r["halluc"].append(v)
    # 错误求和
    if "28000" in text or "相加" in text or "总和" in text:
        r["sum_error"] = True
    return r


models = ["qwen-vl-max", "qwen3-vl-plus", "qwen3.7-plus"]
stats = {m: {"14000": 0, "6000": 0, "1200": 0, "6000_local": 0, "window": 0, "halluc": [], "sum_error": 0} for m in models}

for model in models:
    for i in range(5):
        try:
            r = requests.post(URL, headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"},
                              json={"model": model, "input": {"messages": [{"role": "user", "content": [{"image": du}, {"text": PROMPT}]}]},
                                    "parameters": {"temperature": 0.1, "max_tokens": 600, "vl_high_resolution_images": True}}, timeout=150)
            content = r.json()["output"]["choices"][0]["message"]["content"]
            if isinstance(content, list):
                content = "".join(x.get("text", "") for x in content)
            p = parse(str(content))
            for k in ("14000", "6000", "1200", "6000_local", "window"):
                if p[k]:
                    stats[model][k] += 1
            stats[model]["halluc"].extend(p["halluc"])
            if p["sum_error"]:
                stats[model]["sum_error"] += 1
        except Exception as exc:
            print(f"[{model} 轮{i+1}] 异常: {type(exc).__name__}: {str(exc)[:60]}")

print()
print(f"{'指标':<12} {'VL-Max':<10} {'Qwen3-VL-Plus':<14} {'Qwen3.7-Plus':<14}")
for k, label in [("14000", "14000识别"), ("6000", "6000识别"), ("1200", "1200识别"),
                 ("6000_local", "6000判局部"), ("window", "窗户识别")]:
    print(f"{label:<12} {stats['qwen-vl-max'][k]}/5        {stats['qwen3-vl-plus'][k]}/5            {stats['qwen3.7-plus'][k]}/5")
for m in models:
    h = sorted(set(stats[m]["halluc"]))
    print(f"虚构尺寸 {m:<12}: {h if h else '无'} | 错误求和 {stats[m]['sum_error']}次")
