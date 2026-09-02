from pathlib import Path
import importlib.util
import unittest


BASE = Path(__file__).resolve().parents[1]
SCRIPT = BASE / "_e_identity_live_ab_experiment.py"


def load_module():
    spec = importlib.util.spec_from_file_location("e_identity_live_ab", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class EIdentityLiveABExperimentTests(unittest.TestCase):
    def test_live_script_keeps_single_variable_and_redacts_secret_terms(self):
        mod = load_module()
        self.assertEqual(3, len(mod.CASES))
        self.assertIn("Architectural Reasoning Trace", mod.IDENTITY_TRACE_POLICY)
        self.assertIn("不展示", mod.IDENTITY_TRACE_POLICY)
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertNotIn("sk-", source)
        self.assertNotIn("Authorization", source)

    def test_report_renderer_labels_live_and_compares_ab(self):
        mod = load_module()
        sample = {
            "case": mod.CASES[0],
            "a": {"raw_draft": "A raw", "checked_draft": "A checked", "final_after_boundary": "A final"},
            "b": {"raw_draft": "B raw", "checked_draft": "B checked", "final_after_boundary": "B final"},
        }
        text = mod.build_report([sample])
        self.assertIn("DeepSeek live", text)
        self.assertIn("A：当前筑思 Agent", text)
        self.assertIn("B：Architectural Reasoning Trace", text)
        self.assertIn("不记录 API key", text)


if __name__ == "__main__":
    unittest.main()
