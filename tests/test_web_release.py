from http.server import ThreadingHTTPServer
from pathlib import Path
import subprocess
import tempfile
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


class WebReleaseBuilderTests(unittest.TestCase):
    def test_release_builder_uses_allowlist_and_excludes_private_files(self):
        script = ROOT / "tools" / "build_web_release.ps1"
        with tempfile.TemporaryDirectory() as temp_dir:
            result = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(script),
                    "-SourceRoot",
                    str(ROOT),
                    "-OutputRoot",
                    temp_dir,
                    "-Version",
                    "test-release",
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=30,
            )
            self.assertEqual(0, result.returncode, result.stderr)

            release = Path(temp_dir) / "test-release"
            required = (
                "server.py",
                "requirements.txt",
                "demo/collaborator.html",
                "images/Church_of_the_Light/plan.jpg",
                "vector_db/embeddings.npy",
                "manifest.sha256",
            )
            for relative in required:
                with self.subTest(required=relative):
                    self.assertTrue((release / relative).is_file(), relative)

            forbidden_names = {".env", "vision_raw.log", "server_check.log"}
            forbidden_parts = {"tests", "output", "downloads", "__pycache__"}
            offenders = []
            for path in release.rglob("*"):
                relative = path.relative_to(release)
                if path.name in forbidden_names or any(part in forbidden_parts for part in relative.parts):
                    offenders.append(str(relative))
                if path.is_file() and path.name.startswith("_test_callai_"):
                    offenders.append(str(relative))
            self.assertEqual([], offenders)

            manifest = (release / "manifest.sha256").read_text(encoding="utf-8")
            manifest_paths = [
                line.split("  ", 1)[1]
                for line in manifest.splitlines()
                if "  " in line
            ]
            self.assertIn("server.py", manifest_paths)
            self.assertNotIn(".env", manifest_paths)


if __name__ == "__main__":
    unittest.main()
