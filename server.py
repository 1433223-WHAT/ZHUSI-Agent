"""
server.py — ArchAI Demo 后端代理（Phase 3 生成闭环）

架构：
  demo/index.html (前端)
       ↓ fetch
  server.py (本文件, Python 轻量后端, API key 全在服务端 .env)
       ├── /api/retrieve  → Dify 知识库检索（文本 RAG）
       ├── /api/images    → 图片检索（search_images.py）
       ├── /api/analyze   → 完整闭环：图片 + 文本 → V2.4 Prompt → DeepSeek 生成方案
       └── /api/health    → 健康检查

运行：
  python server.py            # 默认 http://localhost:8787
  python server.py --port 9000

安全：
  - 所有 API key 从 .env 读取，不暴露给前端
  - 支持 CORS，供 demo/index.html 跨端口调用
"""

import json
import os
import sys
import io
import base64
import binascii
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

import requests

# Windows 控制台 UTF-8 输出
if sys.stdout:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

BASE = Path(__file__).resolve().parent

# ── 从 .env 加载配置 ──────────────────────────────────────────────
def _load_env() -> dict:
    env = {}
    env_path = BASE / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            # 剥离行尾注释（# 及其后内容），并清理引号
            v = v.split("#")[0].strip().strip('"').strip("'")
            env[k.strip()] = v
    return env

ENV = _load_env()

DIFY_API_BASE = ENV.get("DIFY_API_BASE", "https://api.dify.ai/v1")
DIFY_API_KEY = ENV.get("DIFY_API_KEY", "")
DIFY_DATASET_ID = ENV.get("DIFY_DATASET_ID", "")       # 案例库
DIFY_THEORY_DATASET = ENV.get("DIFY_THEORY_DATASET", "")  # 理论方法库
DEEPSEEK_API_KEY = ENV.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1/chat/completions"
DEEPSEEK_MODEL = "deepseek-chat"

sys.path.insert(0, str(BASE))
from search_images import search_images  # noqa: E402
from local_search import local_retrieve  # noqa: E402

PROMPT_PATH = BASE / "prompts" / "archai_system_prompt_v2.4.txt"


# ── 核心逻辑 ──────────────────────────────────────────────────────

def dify_retrieve(query: str, top_k: int = 3, dataset_id: str | None = None) -> list[str]:
    """Dify 知识库检索，返回文本片段列表。

    多源检索架构：案例库 + 理论方法库分离，各查一次后拼接。
    - dataset_id 省略时默认查案例库（DIFY_DATASET_ID）
    """
    ds_id = dataset_id or DIFY_DATASET_ID
    if not DIFY_API_KEY or not ds_id:
        return [{"error": "Dify API Key 或 Dataset ID 未配置（见 .env）"}]
    headers = {
        "Authorization": f"Bearer {DIFY_API_KEY}",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0) ArchAI-Server/1.0",
    }
    payload = {
        "query": query,
        "retrieval_model": {
            "search_method": "semantic_search",
            "reranking_enable": True,
            "top_k": top_k,
            "score_threshold_enabled": False,
        },
    }
    resp = requests.post(
        f"{DIFY_API_BASE}/datasets/{ds_id}/retrieve",
        headers=headers, json=payload, timeout=30,
    )
    if resp.status_code != 200:
        return [{"error": f"Dify HTTP {resp.status_code}: {resp.text[:150]}"}]
    records = resp.json().get("records", [])
    return [r.get("segment", {}).get("content", "") for r in records]


def dify_multi_retrieve(query: str, top_k: int = 3) -> dict:
    """双库检索：案例库 + 理论方法库，各查一次。

    Returns:
        {"cases": [...], "theory_methods": [...]} 两个来源的片段
    """
    cases = dify_retrieve(query, top_k, DIFY_DATASET_ID) if DIFY_DATASET_ID else []
    theory_methods = dify_retrieve(query, top_k, DIFY_THEORY_DATASET) if DIFY_THEORY_DATASET else []
    return {"cases": cases, "theory_methods": theory_methods}


def _load_v24_prompt() -> str:
    """旧生成链（/api/analyze、/api/analyze_tools）的 system prompt。

    V1.2 起与筑思对话链隔离：不再要求"生成完整设计方案"（旧 ArchAI 哲学），
    改为筑思定位——按学生请求提供可修改的示范性设计骨架，保留学生决策权。
    """
    if PROMPT_PATH.exists():
        return PROMPT_PATH.read_text(encoding="utf-8")
    return (
        "你是筑思Agent，一名面向建筑专业学生的建筑学习与设计协作助手。\n"
        "学生明确请求设计/框架时，你有义务提供一版可修改、可放弃的示范性设计骨架"
        "（入口/公共区/借阅核心/自习阅览/儿童活动/交通关系的组织），并声明"
        "'可以接受、修改、组合或完全放弃'。骨架属于 AI 建议，不是学生已确认的决定。\n"
        "不替学生拍板：不把 AI 建议写成学生决定，不自动生成不可修改的完整方案。\n"
        "涉及建筑事实（建筑师/年代/尺寸/原文）只能依据检索到的知识，不得编造；"
        "没有合适知识时明确说明是通用设计推演，需后续核实。"
    )


def build_user_message(query: str, multi: dict, images: list[dict]) -> str:
    """拼接用户消息：问题 + 双库检索片段（案例/理论方法）+ 图片策略。

    Args:
        query: 用户问题
        multi: dify_multi_retrieve 的结果 {"cases": [...], "theory_methods": [...]}
        images: 图片检索结果
    """
    cases = [d for d in multi.get("cases", []) if not isinstance(d, dict)]
    theory_methods = [d for d in multi.get("theory_methods", []) if not isinstance(d, dict)]

    cases_block = "\n\n---\n\n".join(cases[:3]) if cases else "（无匹配案例）"
    tm_block = "\n\n---\n\n".join(theory_methods[:3]) if theory_methods else "（无匹配理论/方法）"

    img_lines = []
    for i in images:
        caption = i.get("caption") or i.get("description") or i.get("filename", "")
        strat = i.get("spatial_strategy") or i.get("design_topics", [])[:2]
        img_lines.append(
            f"- [{i.get('case','')}] {caption}\n  图片路径: {i.get('path','')}\n  设计策略: {', '.join(strat)}"
        )
    img_block = "\n".join(img_lines) if img_lines else "（无匹配图片）"

    return f"""【用户问题】
{query}

【案例库检索结果】（参考实例：谁这样设计过）
{cases_block}

【理论与方法库检索结果】（设计原理与方法：为什么、怎么做）
{tm_block}

【相关案例图片及设计策略】（来自 ArchAI Image DB）
{img_block}

请根据以上检索结果，为用户的设计需求提供一版可修改、可放弃的示范性设计骨架。
设计依据应结合：案例佐证（谁这样做过）、理论支撑（为什么有效）、方法操作（具体怎么做）。
骨架属于 AI 建议，不是学生已确认的决定；必须声明"可以接受、修改、组合或完全放弃"。
如果用户的问题属于案例分析/策略迁移/案例比较，请按对应的输出模板回答。"""


def generate_answer(query: str) -> dict:
    """完整闭环：图片检索 + 双库文本检索 + DeepSeek 生成。"""
    # 1. 图片检索
    try:
        images = search_images(query, 4)
    except Exception as e:
        images = [{"error": str(e)}]

    # 2. 双库文本检索（案例库 + 理论方法库）
    multi = dify_multi_retrieve(query)

    # 若任一关键配置缺失，返回错误而非崩溃
    if not DEEPSEEK_API_KEY:
        return {
            "images": images,
            "answer": "⚠️ 服务端未配置 DEEPSEEK_API_KEY（见 .env），无法生成方案。\n"
                      "已完成的检索结果如下，供你预览。",
            "error": "DEEPSEEK_API_KEY missing",
        }

    # 3. 生成
    system_prompt = _load_v24_prompt()
    user_msg = build_user_message(query, multi, images)

    headers = {"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_msg},
        ],
        "temperature": 0.4,
        "max_tokens": 4096,
    }
    try:
        resp = requests.post(DEEPSEEK_BASE_URL, headers=headers, json=payload, timeout=120)
        resp.raise_for_status()
        answer = resp.json()["choices"][0]["message"]["content"]
    except requests.exceptions.HTTPError as e:
        answer = f"⚠️ DeepSeek 调用失败: HTTP {e.response.status_code}: {e.response.text[:200]}"
    except Exception as e:
        answer = f"⚠️ DeepSeek 调用失败: {e}"

    return {"images": images, "answer": answer, "multi": multi}


# ── B 流程：工具增强生成（Agent 工具层）───────────────────────

def build_tool_message(query: str, tool_result: dict, images: list[dict]) -> str:
    """拼接 B 流程用户消息：问题 + 三个工具的结构化返回 + 图片策略。"""
    cases = tool_result.get("cases", [])
    theory = tool_result.get("theory", [])
    methods = tool_result.get("methods", [])

    def fmt_cases():
        lines = []
        for c in cases:
            lines.append(f"- 案例《{c.get('name','')}》 | 策略: {c.get('strategy','')}")
            lines.append(f"  {c.get('content','')[:200]}")
        return "\n".join(lines) if lines else "（无匹配案例）"

    def fmt_theory():
        lines = []
        for t in theory:
            lines.append(f"- 理论《{t.get('name','')}》")
            lines.append(f"  {t.get('content','')[:200]}")
        return "\n".join(lines) if lines else "（无匹配理论）"

    def fmt_methods():
        lines = []
        for m in methods:
            lines.append(f"- 方法《{m.get('name','')}》")
            lines.append(f"  {m.get('content','')[:200]}")
        return "\n".join(lines) if lines else "（无匹配方法）"

    img_lines = []
    for i in images:
        caption = i.get("caption") or i.get("description") or i.get("filename", "")
        strat = i.get("spatial_strategy") or i.get("design_topics", [])[:2]
        img_lines.append(
            f"- [{i.get('case','')}] {caption} | 设计策略: {', '.join(strat)}"
        )
    img_block = "\n".join(img_lines) if img_lines else "（无匹配图片）"

    return f"""【用户问题】
{query}

【案例经验】（本地知识引擎 · 工具返回）
{fmt_cases()}

【理论依据】
{fmt_theory()}

【设计方法】
{fmt_methods()}

【相关案例图片及设计策略】
{img_block}

请基于以上工具检索结果，为用户的建筑设计需求生成一份完整设计方案。
设计依据应结合：案例佐证（谁这样做过）、理论支撑（为什么有效）、方法操作（具体怎么做）。
如果用户的问题属于案例分析/策略迁移/案例比较，请按对应的输出模板回答。"""


def generate_answer_tools(query: str, use_analyzer: bool = True) -> dict:
    """B 流程：Agent 链路（Task Analyzer → Tool Router → 工具 → DeepSeek）。

    已固化到 generator.py，这里只做薄封装（保留 /api/analyze_tools 兼容）。
    """
    from generator import agent_generate
    return agent_generate(query, use_analyzer=use_analyzer)


# ── HTTP 服务 ──────────────────────────────────────────────────────

class ArchAIHandler(BaseHTTPRequestHandler):
    def _send(self, status: int, data: dict):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self._send(204, {})

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/health":
            self._send(200, {"status": "ok", "service": "ArchAI Demo Backend"})
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):
        path = urlparse(self.path).path
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
        except (json.JSONDecodeError, ValueError):
            self._send(400, {"error": "invalid JSON body"})
            return

        try:
            if path == "/api/retrieve":
                query = body.get("query", "")
                multi = dify_multi_retrieve(query, body.get("top_k", 3))
                self._send(200, multi)
            elif path == "/api/local_retrieve":
                query = body.get("query", "")
                if not query:
                    self._send(400, {"error": "query is required"})
                    return
                try:
                    result = local_retrieve(query, body.get("top_k", 3))
                    self._send(200, result)
                except FileNotFoundError as e:
                    self._send(500, {"error": str(e)})
            elif path == "/api/images":
                query = body.get("query", "")
                images = search_images(query, body.get("top_n", 4))
                self._send(200, {"images": images})
            elif path == "/api/analyze":
                query = body.get("query", "")
                if not query:
                    self._send(400, {"error": "query is required"})
                    return
                result = generate_answer(query)
                self._send(200, result)
            elif path == "/api/analyze_tools":
                query = body.get("query", "")
                if not query:
                    self._send(400, {"error": "query is required"})
                    return
                result = generate_answer_tools(query)
                self._send(200, result)
            elif path == "/api/architect_chat":
                message = str(body.get("message", "")).strip()
                history = body.get("history", [])
                state = body.get("state") or {}
                if not message:
                    self._send(400, {"error": "message is required"})
                    return
                if not isinstance(history, list) or not isinstance(state, dict):
                    self._send(400, {"error": "history must be a list and state must be an object"})
                    return
                from architect_chat import chat_turn
                file_contexts = body.get("file_contexts") or []
                if not isinstance(file_contexts, list):
                    self._send(400, {"error": "file_contexts must be a list"})
                    return
                result = chat_turn(message, history, state, body.get("turn_id"), file_contexts=file_contexts)
                self._send(200, result)
            elif path == "/api/parse_document":
                from document_parser import DocumentParseError, parse_document
                filename = str(body.get("filename", "")).strip()
                encoded = body.get("content_base64", "")
                if not filename or not isinstance(encoded, str) or not encoded:
                    self._send(400, {"error": "filename and content_base64 are required"})
                    return
                try:
                    content = base64.b64decode(encoded, validate=True)
                    result = parse_document(filename, content)
                except (ValueError, DocumentParseError) as exc:
                    self._send(400, {"error": str(exc)})
                    return
                self._send(200, result)
            elif path == "/api/analyze_image":
                from image_analyzer import ImageAnalysisError, analyze_architecture_image
                filename = str(body.get("filename", "")).strip()
                encoded = body.get("content_base64", "")
                question = str(body.get("question", "")).strip()
                if not filename or not isinstance(encoded, str) or not encoded:
                    self._send(400, {"error": "filename and content_base64 are required"})
                    return
                try:
                    content = base64.b64decode(encoded, validate=True)
                    result = analyze_architecture_image(filename, content, question)
                except (ValueError, ImageAnalysisError) as exc:
                    self._send(400, {"error": str(exc)})
                    return
                self._send(200, result)
            elif path == "/api/analyze_cross_level":
                # 多图联合分析：两层/多张图对齐轴网，产出楼层对应关系
                from image_analyzer import analyze_cross_level
                images = body.get("images") or []
                if not isinstance(images, list) or len(images) < 2:
                    self._send(400, {"error": "images must be a list with at least 2 items"})
                    return
                files = []
                try:
                    for item in images[:4]:
                        filename = str(item.get("filename", "")).strip()
                        encoded = str(item.get("content_base64", ""))
                        if not filename or not encoded:
                            raise ValueError("each image needs filename and content_base64")
                        data = base64.b64decode(encoded, validate=True)
                        ext = Path(filename).suffix.lower()
                        mime = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "webp": "image/webp"}.get(ext.lstrip("."), "image/png")
                        files.append({"filename": filename, "data": data, "mime_type": mime})
                except (ValueError, binascii.Error) as exc:
                    self._send(400, {"error": str(exc)})
                    return
                result = analyze_cross_level(files)
                self._send(200, result)
            elif path == "/api/propose_directions":
                # 提案 3 个设计方向（Human-in-the-loop 第一步）
                query = body.get("query", "")
                if not query:
                    self._send(400, {"error": "query is required"})
                    return
                from direction_proposer import propose_directions
                answers = body.get("answers") or []
                design_context = body.get("design_context")
                result = propose_directions(query, answers=answers, design_context=design_context)
                self._send(200, result)
            elif path == "/api/design_loop":
                # 完整设计推演：分析→知识→初稿→评审→优化（供 UI 展示）
                query = body.get("query", "")
                if not query:
                    self._send(400, {"error": "query is required"})
                    return
                from design_critic import full_design_loop
                user_choice = body.get("user_choice")
                directions = body.get("directions")
                result = full_design_loop(
                    query,
                    user_choice=user_choice,
                    directions=directions,
                    design_context=body.get("design_context"),
                )
                self._send(200, result)
            elif path == "/api/deepen":
                # 深化助手：方向 + 深化维度 → 针对性建议
                query = body.get("query", "")
                direction = body.get("direction")
                dimension = body.get("dimension", "material")
                if not query or not direction:
                    self._send(400, {"error": "query and direction are required"})
                    return
                from deepen_assistant import deepen
                result = deepen(query, direction, dimension)
                self._send(200, result)
            elif path == "/api/mentor_ask":
                # 设计导师：AI 主动提问
                query = body.get("query", "")
                if not query:
                    self._send(400, {"error": "query is required"})
                    return
                from design_mentor import mentor_ask
                result = mentor_ask(query)
                self._send(200, result)
            elif path == "/api/mentor_adjust":
                # 设计导师：根据学生回答调整方向
                query = body.get("query", "")
                answers = body.get("answers", [])
                directions = body.get("directions", [])
                if not query or not directions:
                    self._send(400, {"error": "query and directions are required"})
                    return
                from design_mentor import mentor_adjust
                result = mentor_adjust(query, answers, directions)
                self._send(200, result)
            elif path == "/api/feedback":
                # 设计反馈循环：学生自由反馈 → AI 调整方案（版本迭代 + 对比）
                query = body.get("query", "")
                current_solution = body.get("current_solution", "")
                feedback = body.get("feedback", "")
                review = body.get("review")
                if not query or not current_solution or not feedback:
                    self._send(400, {"error": "query, current_solution and feedback are required"})
                    return
                from design_critic import revise_with_diff
                result = revise_with_diff(
                    query,
                    current_solution,
                    feedback,
                    review or {"score": 0, "strengths": [], "problems": [], "revision": []},
                    version_number=body.get("version_number", 2),
                    selected_direction=body.get("selected_direction") or {},
                    parent_version=body.get("parent_version", 1),
                )
                self._send(200, result)
            elif path == "/api/discuss_assess":
                # 设计讨论层：评估当前理解状态（分项进度）
                query = body.get("query", "")
                discussion = body.get("discussion", [])
                if not query:
                    self._send(400, {"error": "query is required"})
                    return
                from design_discussion import assess_understanding
                result = assess_understanding(
                    query, discussion, body.get("known_facts", {}), body.get("previous_percent", 0),
                    body.get("known_fact_states", {}), body.get("answer_dimension", ""),
                )
                self._send(200, result)
            elif path == "/api/discuss_ask":
                # 设计讨论层：AI 追问下一个关键问题（单轮）
                query = body.get("query", "")
                discussion = body.get("discussion", [])
                understanding = body.get("understanding", {})
                if not query:
                    self._send(400, {"error": "query is required"})
                    return
                from design_discussion import ask_next_question
                result = ask_next_question(
                    query, discussion, understanding, body.get("asked_questions", [])
                )
                self._send(200, result)
            else:
                self._send(404, {"error": "not found"})
        except Exception as e:
            self._send(500, {"error": str(e)})

    def log_message(self, format, *args):
        sys.stderr.write(f"[ArchAI] {args[0]}\n")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="ArchAI Demo Backend")
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()

    if not DIFY_API_KEY:
        print("⚠ 警告: DIFY_API_KEY 未配置，/api/retrieve 与 /api/analyze 将无法检索知识库")
    if not DEEPSEEK_API_KEY:
        print("⚠ 警告: DEEPSEEK_API_KEY 未配置，/api/analyze 将无法生成方案")

    server = ThreadingHTTPServer((args.host, args.port), ArchAIHandler)
    print(f"ArchAI Demo Backend 运行中 → http://{args.host}:{args.port}")
    print("  GET  /api/health")
    print("  POST /api/retrieve   {query}")
    print("  POST /api/images     {query, top_n}")
    print("  POST /api/analyze    {query}  ← 完整闭环（图片+文本+生成）")
    print("按 Ctrl+C 停止")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")


if __name__ == "__main__":
    main()
