import importlib.util
from pathlib import Path
import tempfile
import unittest


BASE = Path(__file__).resolve().parents[1]
SCRIPT = BASE / "_e_identity_ab_experiment.py"


def load_module():
    spec = importlib.util.spec_from_file_location("e_identity_ab", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class EIdentityABExperimentTests(unittest.TestCase):
    def test_builds_three_local_ab_cases_without_network_dependencies(self):
        mod = load_module()
        self.assertEqual(3, len(mod.CASES))
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertNotIn("requests", source)
        self.assertNotIn("DEEPSEEK", source)

    def test_writes_markdown_with_normal_and_identity_chain_outputs(self):
        mod = load_module()
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "e_identity_ab.md"
            mod.write_report(out)
            text = out.read_text(encoding="utf-8")
        self.assertIn("# E2 高风险经验跳跃 A/B 本地 Prompt 实验", text)
        self.assertEqual(3, text.count("## 案例"))
        self.assertIn("### A：普通生成 Prompt", text)
        self.assertIn("### B：高风险经验跳跃检查 Prompt", text)
        self.assertIn("只检查三类高风险经验跳跃", text)
        self.assertIn("不跑 live model", text)
        self.assertNotIn("项目事实 / AI观察 / 条件假设 / 设计建议 / 学生决定", text)


if __name__ == "__main__":
    unittest.main()
