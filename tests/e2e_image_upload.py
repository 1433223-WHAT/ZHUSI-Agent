import io
import json
import tempfile
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from PIL import Image, ImageDraw
from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]


with tempfile.TemporaryDirectory() as temp_dir:
    image_path = Path(temp_dir) / "场地草图.png"
    image = Image.new("RGB", (640, 420), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((40, 40, 600, 380), outline="black", width=5)
    image.save(image_path)

    handler = partial(SimpleHTTPRequestHandler, directory=str(ROOT))
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{httpd.server_port}/demo/collaborator.html"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 800})
        errors = []
        page.on("pageerror", lambda exc: errors.append(str(exc)))
        page.on("dialog", lambda dialog: dialog.accept())

        def analyze_handler(route):
            request = json.loads(route.request.post_data)
            assert request["question"] == "请分析入口与人流，但不要猜测尺寸"
            route.fulfill(status=200, content_type="application/json", body=json.dumps({
                "filename": request["filename"], "extension": ".png", "mime_type": "image/png",
                "size_bytes": 2048, "width": 640, "height": 420, "status": "analyzed",
                "image_type": "sketch", "error": "",
                "visible_facts": ["图中可见一个矩形边界"],
                "inferences": [{"content": "可能表示场地边界", "basis": "封闭矩形线条", "confidence": "medium"}],
                "unknowns": ["无法确认比例和真实尺寸"],
                "architecture_questions": ["入口准备设置在哪一侧？"], "warnings": [],
            }, ensure_ascii=False))

        page.route("**/api/analyze_image", analyze_handler)
        page.goto(base, wait_until="networkidle")
        page.fill("#input", "请分析入口与人流，但不要猜测尺寸")
        page.locator("#fileInput").set_input_files(str(image_path))
        page.wait_for_function("!document.querySelector('#attachBtn').disabled")

        files = page.locator("#filesContent")
        assert files.get_by_text("图片中明确可见", exact=True).count() == 1
        assert files.get_by_text("图中可见一个矩形边界", exact=False).count() == 1
        assert files.get_by_text("AI推测（不是已确认事实）", exact=True).count() == 1
        assert files.get_by_text("可能表示场地边界", exact=False).count() == 1
        assert files.get_by_text("无法确认比例和真实尺寸", exact=False).count() == 1
        assert files.get_by_text("入口准备设置在哪一侧", exact=False).count() == 1
        assert "可能表示场地边界" not in page.locator("#memoryContent").inner_text()
        assert not errors, errors
        browser.close()

    httpd.shutdown()
    httpd.server_close()

print(json.dumps({"status": "ok", "flow": "image-consent-analysis-separation"}, ensure_ascii=False))
