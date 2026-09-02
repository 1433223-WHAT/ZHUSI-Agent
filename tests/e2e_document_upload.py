import base64
import json
import tempfile
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]


with tempfile.TemporaryDirectory() as temp_dir:
    task_file = Path(temp_dir) / "大学生活动中心任务书.txt"
    task_file.write_text("总建筑面积约3500平方米，建筑限高18米。", encoding="utf-8")

    handler = partial(SimpleHTTPRequestHandler, directory=str(ROOT))
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    server_thread.start()
    base = f"http://127.0.0.1:{httpd.server_port}/demo/collaborator.html"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 800})
        errors = []
        page.on("pageerror", lambda exc: errors.append(str(exc)))

        def parse_handler(route):
            request = json.loads(route.request.post_data)
            content = base64.b64decode(request["content_base64"]).decode("utf-8")
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps({
                    "filename": request["filename"], "extension": ".txt", "mime_type": "text/plain",
                    "size_bytes": len(content.encode()), "status": "parsed", "text": content,
                    "character_count": len(content), "page_count": None, "truncated": False,
                    "message": "文档解析完成。",
                }, ensure_ascii=False),
            )

        def chat_handler(route):
            request = json.loads(route.request.post_data)
            assert len(request["file_contexts"]) == 1
            assert request["file_contexts"][0]["filename"] == "大学生活动中心任务书.txt"
            source = {
                "id": request["file_contexts"][0]["id"], "filename": "大学生活动中心任务书.txt",
                "kind": "document", "source": "document", "status": "reference_only",
                "excerpt": "总建筑面积约3500平方米",
            }
            state = {
                "project": {key: {} for key in ("project_type", "site", "users", "functions", "scale", "goals", "constraints")},
                "student_decisions": [], "student_intent": [], "conflicts": [], "change_log": [], "versions": [],
                "source_records": [source], "knowledge_annotations": [],
                "interaction_log": [{
                    "turn_id": 1, "student_message": request["message"],
                    "ai_reply": "任务书写明总建筑面积约3500平方米，但这仍是文件资料。",
                    "ai_source": "ai", "is_student_decision": False, "file_ids": [source["id"]],
                    "knowledge_ids": [], "model_status": "ok",
                }],
            }
            route.fulfill(status=200, content_type="application/json", body=json.dumps({
                "reply": "任务书写明总建筑面积约3500平方米，但这仍是文件资料。",
                "state": state, "knowledge_annotations": [], "model_status": "ok", "retrieval_status": "not_needed",
            }, ensure_ascii=False))

        page.route("**/api/parse_document", parse_handler)
        page.route("**/api/architect_chat", chat_handler)
        page.goto(base, wait_until="networkidle")
        page.locator("#fileInput").set_input_files(str(task_file))
        page.wait_for_function("!document.querySelector('#attachBtn').disabled")

        assert page.locator('[data-tab="files"]').evaluate("el => el.classList.contains('active')")
        assert page.get_by_text("大学生活动中心任务书.txt", exact=True).count() == 1
        assert page.get_by_text("总建筑面积约3500平方米", exact=False).count() == 1
        assert page.get_by_text("解析完成", exact=True).count() == 1
        assert "大学生活动中心任务书" not in page.locator("#memoryContent").inner_text()

        page.get_by_role("button", name="用于后续对话").click()
        assert page.get_by_role("button", name="正在用于后续对话").count() == 1
        page.fill("#input", "这份任务书对面积有什么要求？")
        page.click("#sendBtn")
        page.wait_for_function("!document.querySelector('#sendBtn').disabled")
        assert page.locator("#memoryContent").get_by_text("文档资料", exact=True).count() == 1
        assert page.locator("#memoryContent").get_by_text("仅供参考", exact=True).count() == 1
        assert "3500" not in page.locator("#memoryContent").inner_text()
        page.get_by_role("button", name="过程记录").click()
        assert page.locator("#processContent").get_by_text("使用文件 1", exact=True).count() == 1
        assert page.locator("#processContent").get_by_text("AI内容未确认为决定", exact=True).count() == 1

        page.reload(wait_until="networkidle")
        page.get_by_role("button", name="项目文件").click()
        assert page.get_by_text("大学生活动中心任务书.txt", exact=True).count() == 1
        assert not errors, errors
        browser.close()
    httpd.shutdown()
    httpd.server_close()

print(json.dumps({"status": "ok", "flow": "document-upload-preview-persist"}, ensure_ascii=False))
