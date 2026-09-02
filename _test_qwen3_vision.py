# -*- coding: utf-8 -*-
"""对比 qwen-vl-max vs qwen3-vl-plus 的合成图尺寸识别。"""
import sys, io, base64
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
import requests

KEY = ""
path = r"E:\AI\项目设计\筑智AI_ArchAI\ArchAI_Builder\.env"
for line in open(path, encoding="utf-8"):
    if line.strip().startswith("DASHSCOPE_API_KEY="):
        KEY = line.split("=", 1)[1].split("#", 1)[0].strip().strip('"').strip("'")

URL = "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation"
img = open(r"E:\AI\项目设计\筑智AI_ArchAI\ArchAI_Builder\_test_dims.png", "rb").read()
du = "data:image/png;base64," + base64.b64encode(img).decode("ascii")

PROMPT = """你是筑思Agent的建筑图像阅读工具。请只返回JSON对象：
{
  "visible_facts": ["图片中明确可见、可直接描述的事实"],
  "dimension_annotations": ["图中检测到的所有尺寸/数字标注，只列数字与位置描述，不做对象绑定判断"],
  "unknowns": []
}
必须把观察和推测分开。"""

for model in ["qwen-vl-max", "qwen3-vl-plus"]:
    try:
        r = requests.post(URL, headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"},
                          json={"model": model, "input": {"messages": [{"role": "user", "content": [{"image": du}, {"text": PROMPT}]}]},
                                "parameters": {"temperature": 0.1, "max_tokens": 1000}}, timeout=120)
        content = r.json()["output"]["choices"][0]["message"]["content"]
        if isinstance(content, list):
            content = "".join(x.get("text", "") for x in content)
        print(f"===== {model} =====")
        # 打印 dimension_annotations 相关
        import re
        m = re.search(r'"dimension_annotations"\s*:\s*(\[[^\]]*\])', content)
        print("dimension_annotations:", m.group(1)[:400] if m else "(未输出)")
        # 总尺寸相关
        if "14000" in content and "28000" not in content:
            print("含 14000 ✓，无 28000 ✓")
        print()
    except Exception as exc:
        print(f"{model} 异常: {type(exc).__name__}: {str(exc)[:120]}")
