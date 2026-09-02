from pathlib import Path
import importlib.util
import tempfile
import unittest


BASE = Path(__file__).resolve().parents[1]
SCRIPT = BASE / "_f3_identity_design_labor_balance_experiment.py"


def load_module():
    spec = importlib.util.spec_from_file_location("f3_balance", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class F3IdentityDesignLaborBalanceExperimentTests(unittest.TestCase):
    def test_local_experiment_has_three_cases_without_network_or_agent_chain(self):
        mod = load_module()
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertEqual(3, len(mod.CASES))
        self.assertNotIn("requests", source)
        self.assertNotIn("DEEPSEEK", source)
        self.assertNotIn("api.deepseek", source)
        self.assertNotIn("chat_turn", source)
        self.assertNotIn("SYSTEM_PROMPT", source)
        self.assertIn("设计劳动平衡", source)

    def test_report_contains_required_f3_judgment(self):
        mod = load_module()
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "f3.md"
            mod.write_report(out)
            text = out.read_text(encoding="utf-8")
        self.assertIn("# F3 身份链 + 设计劳动平衡实验", text)
        self.assertEqual(3, text.count("## Case "))
        self.assertIn("A 身份漂移", text)
        self.assertIn("B 身份漂移", text)
        self.assertIn("A 设计劳动", text)
        self.assertIn("B 设计劳动", text)
        self.assertIn("身份漂移：\n下降", text)
        self.assertIn("设计劳动：\n保持", text)
        self.assertIn("免责声明：", text)
        self.assertIn("最终：\n支持", text)


if __name__ == "__main__":
    unittest.main()
