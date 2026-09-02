import json
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]
SHOT = ROOT / "demo" / "collaborator-e2e.png"


def fulfill(route, payload):
    route.fulfill(status=200, content_type="application/json", body=json.dumps(payload, ensure_ascii=False))


def state(project_type="", users="", knowledge=None, changes=None, versions=None):
    project = {key: {} for key in ("project_type", "site", "users", "functions", "scale", "goals", "constraints")}
    if project_type:
        project["project_type"] = {"value": project_type, "status": "confirmed", "source": "student"}
    if users:
        project["users"] = {"value": users, "status": "confirmed", "source": "student"}
    return {
        "project": project, "student_intent": [], "student_decisions": [], "ai_suggestions": [],
        "assumptions": [], "unresolved_questions": [], "conflicts": [],
        "knowledge_used": knowledge or [], "question_history": [], "change_log": changes or [],
        "versions": versions or [], "current_stage": "探索", "pending_clarification": "",
    }


handler = partial(SimpleHTTPRequestHandler, directory=str(ROOT))
httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
threading.Thread(target=httpd.serve_forever, daemon=True).start()
base = f"http://127.0.0.1:{httpd.server_port}/demo/collaborator.html"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    errors = []
    page.on("pageerror", lambda exc: errors.append(str(exc)))
    count = {"value": 0}

    def handler(route):
        count["value"] += 1
        n = count["value"]
        if n == 1:
            fulfill(route, {"reply": "可以。这个博物馆希望主要服务哪些人？<script>window.bad=1</script>", "intent": "project_brief", "state": state("博物馆"), "knowledge": [], "model_called": True, "model_status": "ok", "retrieval_status": "not_needed"})
        elif n == 2:
            s = state("博物馆", "普通市民")
            fulfill(route, {"reply": "公共性会影响入口、展陈和停留空间。", "intent": "general_architecture_chat", "state": s, "knowledge": [], "model_called": True, "model_status": "ok", "retrieval_status": "not_needed"})
        elif n == 3:
            s = state("博物馆", "所有群体", changes=[{"dimension": "users", "from": "普通市民", "to": "所有群体"}])
            fulfill(route, {"reply": "已把上一题修改为面向所有群体。", "intent": "modify_previous_answer", "state": s, "knowledge": [], "model_called": True, "model_status": "ok", "retrieval_status": "not_needed"})
        elif n == 4:
            knowledge = [{"type": "case", "name": "金贝尔艺术博物馆", "strategy": "顶光组织", "source_text": "拱形顶棚调节自然光。", "status": "verified_source"}]
            annotations = [{
                "id": "turn-7-source-1", "turn_id": 7, "type": "case", "name": "金贝尔艺术博物馆",
                "original_strategy": "拱顶漫射自然光", "source_text": "自然光经反射板进入展厅。",
                "relevance": "与本轮采光问题相关。", "transferable": "可参考漫射采光方法。",
                "boundary": "不可忽略当前场地朝向。", "risk": "尺度不同可能失效。",
                "verification_status": "verified_source",
            }]
            s = state("博物馆", "所有群体", knowledge=knowledge, changes=[{"dimension": "users", "from": "普通市民", "to": "所有群体"}])
            s["knowledge_annotations"] = annotations
            fulfill(route, {"reply": "可以研究金贝尔艺术博物馆的顶光组织。", "intent": "analyze_case", "state": s, "knowledge": knowledge, "knowledge_annotations": annotations, "model_called": True, "model_status": "ok", "retrieval_status": "matched"})
        else:
            versions = [{"number": 1, "content": "# 阶段成果 V1\n学生决定以公共性为核心。"}]
            s = state("博物馆", "所有群体", versions=versions)
            fulfill(route, {"reply": "# 阶段成果 V1\n这是基于学生当前决定的整理。", "intent": "create_version", "state": s, "knowledge": [], "model_called": True, "model_status": "ok", "retrieval_status": "not_needed"})

    page.route("**/api/architect_chat", handler)
    page.goto(base, wait_until="networkidle")
    for message in ("我想做一个博物馆", "普通市民", "上一个问题修改为所有群体", "分析金贝尔艺术博物馆的采光", "整理当前思路并形成阶段性 V1"):
        page.fill("#input", message)
        page.click("#sendBtn")
        page.wait_for_timeout(80)
        page.wait_for_function("!document.querySelector('#sendBtn').disabled")

    assert page.evaluate("window.bad") is None
    assert page.locator("#memoryContent").get_by_text("博物馆", exact=False).count() >= 1
    assert page.locator("#memoryContent").get_by_text("所有群体", exact=False).count() >= 1
    evidence_button = page.get_by_role("button", name="查看知识注释 · 1")
    assert evidence_button.count() == 1
    evidence_button.click()
    assert page.locator('[data-tab="knowledge"]').evaluate("el => el.classList.contains('active')")
    assert page.locator("#knowledgeContent").get_by_text("自然光经反射板进入展厅", exact=False).count() == 1
    assert page.locator(".message .bubble").get_by_text("自然光经反射板进入展厅", exact=False).count() == 0
    page.get_by_role("button", name="过程记录").click()
    assert page.get_by_text("阶段成果 V1", exact=False).count() >= 1
    page.reload(wait_until="networkidle")
    assert page.get_by_text("上一个问题修改为所有群体", exact=False).count() >= 1
    assert page.get_by_role("button", name="查看知识注释 · 1").count() == 1
    long_plan = "\n\n".join(
        f"## 第{i}部分\n空间组织、场地回应、功能流线、材料策略和自然采光需要逐项说明。" * 8
        for i in range(1, 101)
    )
    page.evaluate('(text) => add("assistant", text, "长方案滚动测试")', long_plan)
    scroll_metrics = page.evaluate("""() => {
        const messages = document.querySelector('#messages');
        const workspace = document.querySelector('.workspace');
        return {
            scrollHeight: messages.scrollHeight,
            clientHeight: messages.clientHeight,
            messagesHeight: messages.getBoundingClientRect().height,
            workspaceHeight: workspace.getBoundingClientRect().height,
        };
    }""")
    assert scroll_metrics["scrollHeight"] > scroll_metrics["clientHeight"]
    assert scroll_metrics["messagesHeight"] <= scroll_metrics["workspaceHeight"]
    page.locator("#messages").hover()
    page.mouse.wheel(0, -10000)
    page.mouse.wheel(0, 1200)
    page.wait_for_timeout(100)
    assert page.evaluate("document.querySelector('#messages').scrollTop") > 0
    with page.expect_download() as download_info:
        page.get_by_title("导出设计过程").click()
    assert download_info.value.suggested_filename.endswith(".md")
    page.set_viewport_size({"width": 390, "height": 844})
    assert page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")
    page.screenshot(path=str(SHOT), full_page=True)
    assert not errors, errors
    browser.close()

httpd.shutdown()
httpd.server_close()

print(json.dumps({"status": "ok", "screenshot": str(SHOT)}, ensure_ascii=False))
