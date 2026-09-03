from http.server import ThreadingHTTPServer
from pathlib import Path
import threading
import unittest

import requests

from server import ArchAIHandler


ROOT = Path(__file__).resolve().parents[1]


class SingleOriginWebReleaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), ArchAIHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        host, port = cls.server.server_address
        cls.base_url = f"http://{host}:{port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=3)

    def test_root_serves_collaborator_html(self):
        response = requests.get(self.base_url + "/", timeout=3)

        self.assertEqual(200, response.status_code)
        self.assertIn("筑思", response.text)
        self.assertIn("text/html", response.headers.get("Content-Type", ""))

    def test_demo_page_is_served_from_backend_origin(self):
        response = requests.get(self.base_url + "/demo/collaborator.html", timeout=3)

        self.assertEqual(200, response.status_code)
        self.assertIn("筑思", response.text)

    def test_case_image_is_served_with_image_mime_type(self):
        response = requests.get(
            self.base_url + "/images/Church_of_the_Light/plan.jpg", timeout=3
        )

        self.assertEqual(200, response.status_code)
        self.assertEqual("image/jpeg", response.headers.get("Content-Type"))
        self.assertGreater(len(response.content), 100)

    def test_static_routes_do_not_expose_env_or_parent_paths(self):
        for path in ("/.env", "/demo/%2e%2e/.env", "/images/%2e%2e/.env"):
            with self.subTest(path=path):
                response = requests.get(self.base_url + path, timeout=3)
                self.assertIn(response.status_code, (403, 404))
                self.assertNotIn("DEEPSEEK_API_KEY", response.text)

    def test_same_origin_responses_do_not_enable_wildcard_cors(self):
        response = requests.get(self.base_url + "/api/health", timeout=3)

        self.assertEqual(200, response.status_code)
        self.assertNotEqual("*", response.headers.get("Access-Control-Allow-Origin"))

    def test_collaborator_uses_relative_same_origin_urls(self):
        source = (ROOT / "demo" / "collaborator.html").read_text(encoding="utf-8")

        self.assertIn('API="/api/architect_chat"', source)
        self.assertIn('IMG_BASE=""', source)
        self.assertNotIn('http://"+HOST+":8787', source)
        self.assertNotIn(':8787/api/', source)
        self.assertNotIn(':8000', source)


if __name__ == "__main__":
    unittest.main()
