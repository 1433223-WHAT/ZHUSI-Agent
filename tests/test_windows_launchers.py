from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class WindowsLauncherContractTests(unittest.TestCase):
    def test_start_script_has_reliable_preflight_and_health_checks(self):
        script = (ROOT / "启动Demo.bat").read_text(encoding="utf-8-sig")

        required_markers = [
            "PYTHON_EXE",
            "requirements.txt",
            "Get-NetTCPConnection",
            "/api/health",
            "Invoke-WebRequest",
            "demo/collaborator.html",
        ]
        for marker in required_markers:
            with self.subTest(marker=marker):
                self.assertIn(marker, script)

        self.assertNotIn("timeout /t 3", script.lower())
        self.assertNotIn('cmd /k "python ', script.lower())
        self.assertIn("BACKEND_PORT=8787", script)
        self.assertIn("http://127.0.0.1:%BACKEND_PORT%/demo/collaborator.html", script)
        self.assertNotIn("FRONTEND_PORT", script)
        self.assertNotIn("http.server", script)

    def test_stop_script_is_scoped_to_project_ports_and_python(self):
        script = (ROOT / "停止筑思Agent.bat").read_text(encoding="utf-8-sig")

        self.assertIn("$ports=8787", script)
        self.assertNotIn("8000", script)
        self.assertIn("python", script.lower())
        self.assertIn("Read-Host", script)
        self.assertIn("Stop-Process", script)

    def test_readme_matches_current_product_and_entrypoint(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8-sig")

        self.assertIn("学生保留判断、选择、修改和最终决定", readme)
        self.assertIn("demo/collaborator.html", readme)
        self.assertIn("停止筑思Agent.bat", readme)
        self.assertIn("真实限制", readme)
        self.assertNotIn("生成完整方案", readme)


if __name__ == "__main__":
    unittest.main()
