# -*- coding: utf-8 -*-
"""端到端冒烟测试 —— 只回答一个问题：「我这套环境到底装对了没有？」

【什么时候需要它】
  1. 配好 .env（填了 API Key）并启动服务之后，想确认是不是真能问答；
  2. 有人反馈「跑不起来」时，用它快速定位断在哪一环。
  跑出来四项全绿，就不用再管这个文件了。

【怎么跑】两步，两个命令行窗口
  第一步：启动服务
      Windows 上直接双击「启动Demo.bat」；
      或命令行执行 python server.py --host 127.0.0.1 --port 8787
  第二步：等服务启动完成后，**另开一个**命令行窗口，在本文件所在目录执行
      python _smoke_test.py

【它检查什么】依次四项，每项打印「通过 / 失败 / 跳过」
  [1] 健康检查       —— 服务有没有活着。这一项不过就直接退出，先去启动服务。
  [2] 本地知识库检索 —— 内置知识库能不能检索到内容。
                        没装 torch / transformers 时显示「跳过」，属正常，
                        不影响对话等其它功能。
  [3] 核心对话问答   —— 拿一句真实的学生提问去问 AI，看有没有真的回答出来。
  [4] 带资料上下文   —— 模拟上传一份任务书，看 AI 会不会用上这份资料。

【结果怎么看】
  · 四项全「通过」            → 环境正常，可以正常使用。
  · [1] 失败                 → 服务没起来。看启动窗口的报错，通常是端口被占用
                                （换端口：python server.py --port 8899）或依赖没装。
  · [3] / [4] 失败           → 多半是 API Key 填错、余额不足或网络不通。
                                脚本会把 AI 返回的原文打印出来，照着报错排查即可。
  · [2] 跳过                 → 只是没装可选依赖，不是故障。

【其它】
  · 只依赖 requests，核心依赖里已包含，不需要额外安装任何东西。
  · 第 [3][4] 项会真实调用一次大模型，消耗极少量额度（每次约几千 token），
    不是本地模拟，跑一次就见效。
  · 内置的问题是《补园记》示例，仅用于验证链路，不会写入你的项目数据。
"""
import json
import os
import sys
import time
import urllib.request

BASE = "http://127.0.0.1:8787"
PKG = os.path.dirname(os.path.abspath(__file__))


def post(path, payload, timeout=180):
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        BASE + path, data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8")), time.time() - t0


def get(path, timeout=30):
    with urllib.request.urlopen(BASE + path, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def ok(x):
    return "\033[92m通过\033[0m" if x else "\033[91m失败\033[0m"


def skip():
    return "\033[93m跳过\033[0m"


print("=" * 70)
print("筑思 Agent 可运行程序 —— 端到端冒烟测试")
print("=" * 70)

# 1) 健康检查
try:
    h = get("/api/health")
    print(f"[1] 健康检查        : {ok(h.get('status')=='ok')}  {h}")
except Exception as e:
    print(f"[1] 健康检查        : {ok(False)}  {e}")
    sys.exit(1)

# 2) 本地知识库检索（无需 Key，验证内置数据可用）
try:
    r, dt = post("/api/local_retrieve", {"query": "留园 石林小院 空间序列", "top_k": 3})
    if r.get("available") is False:
        # 可选依赖 torch/transformers 未安装：本地向量检索降级，核心功能不受影响
        print(f"[2] 本地知识库检索  : {skip()}  （可选依赖未安装）{r.get('reason', '')}")
        print("      需要时执行：pip install -r requirements-full.txt 后重启服务")
    else:
        groups = {k: (v or []) for k, v in r.items() if isinstance(v, list)}
        hits = sum(len(v) for v in groups.values())
        print(f"[2] 本地知识库检索  : {ok(hits>0)}  命中 {hits} 条 / {dt:.1f}s  {[f'{k}:{len(v)}' for k,v in groups.items()]}")
        for k, v in groups.items():
            for it in v[:2]:
                t = it.get("name") or it.get("title") or str(it)[:60]
                print(f"      · [{k}] {t}")
except Exception as e:
    print(f"[2] 本地知识库检索  : {ok(False)}  {e}")

# 3) 核心对话（走 DeepSeek，验证 Key 生效 + 能出回答）
q1 = "老师发了《补园记》任务书，基地是留园石林小院原址，37.5m×16.5m。我完全看不懂这题要我做什么，你先帮我拆一下。"
try:
    r, dt = post("/api/architect_chat", {"message": q1, "history": [], "state": {}, "file_contexts": []})
    reply = (r.get("reply") or r.get("answer") or "").strip()
    good = len(reply) > 80 and "失败" not in reply[:20] and "调用失败" not in reply
    print(f"[3] 核心对话问答    : {ok(good)}  {len(reply)} 字 / {dt:.1f}s")
    print("      --- 回答开头 ---")
    print("      " + reply[:220].replace("\n", "\n      "))
except Exception as e:
    print(f"[3] 核心对话问答    : {ok(False)}  {e}")

# 4) 带文件上下文（验证上传任务书后的解读链路）
txt = ("《补园记》课程设计任务书\n"
       "基地：苏州留园石林小院原址，37.5m × 16.5m，约 620 平方米。\n"
       "主题：以中国传统山水画为参照，完成一处园林空间的当代转译。\n"
       "阶段：一「像」、二「画」、三「境」、四「园」，共 8 周。\n"
       "成果：不少于 2 张 A1 图纸 + 过程模型。")
try:
    r, dt = post("/api/architect_chat", {
        "message": "这是任务书，帮我整理成一张硬要求清单：哪些是明文写死的，哪些还要去问老师？",
        "history": [], "state": {},
        "file_contexts": [{"kind": "document", "filename": "补园记任务书.txt", "content": txt}],
    })
    reply = (r.get("reply") or r.get("answer") or "").strip()
    good = len(reply) > 80 and "调用失败" not in reply
    print(f"[4] 带资料上下文    : {ok(good)}  {len(reply)} 字 / {dt:.1f}s")
    print("      --- 回答开头 ---")
    print("      " + reply[:220].replace("\n", "\n      "))
except Exception as e:
    print(f"[4] 带资料上下文    : {ok(False)}  {e}")

print("=" * 70)
