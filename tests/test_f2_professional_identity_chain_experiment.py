from pathlib import Path
import importlib.util
import tempfile
import unittest


BASE = Path(__file__).resolve().parents[1]
SCRIPT = BASE / "_f2_professional_identity_chain_experiment.py"


def load_module():
    spec = importlib.util.spec_from_file_location("f2_identity_chain", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class F2ProfessionalIdentityChainExperimentTests(unittest.TestCase):
    def test_local_experiment_has_three_cases_without_network(self):
        mod = load_module()
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertEqual(3, len(mod.CASES))
        self.assertNotIn("requests", source)
        self.assertNotIn("DEEPSEEK", source)
        self.assertNotIn("api.deepseek", source)
        self.assertNotIn("chat_turn", source)
        self.assertNotIn("SYSTEM_PROMPT", source)
        self.assertIn("专业经验身份链", source)

    def test_report_matches_f2_acceptance_shape(self):
        mod = load_module()
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "f2.md"
            mod.write_report(out)
            text = out.read_text(encoding="utf-8")
        self.assertIn("# F2 专业经验身份链实验", text)
        self.assertEqual(3, text.count("## Case "))
        self.assertIn("Case 1 类型经验", text)
        self.assertIn("Case 2 建筑经验", text)
        self.assertIn("Case 3 技术经验", text)
        self.assertIn("B 组未五栏化", text)
        self.assertIn("最终：", text)
        self.assertIn("支持", text)


if __name__ == "__main__":
    unittest.main()
