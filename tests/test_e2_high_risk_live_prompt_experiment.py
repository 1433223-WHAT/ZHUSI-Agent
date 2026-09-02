from pathlib import Path
import importlib.util
import unittest


BASE = Path(__file__).resolve().parents[1]
SCRIPT = BASE / "_e2_high_risk_live_prompt_experiment.py"


def load_module():
    spec = importlib.util.spec_from_file_location("e2_live", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class E2HighRiskLivePromptExperimentTests(unittest.TestCase):
    def test_script_is_minimal_prompt_ab_not_full_agent(self):
        mod = load_module()
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertEqual(3, len(mod.CASES))
        self.assertIn("高风险经验跳跃", mod.E2_POLICY)
        self.assertNotIn("_call_deepseek", source)
        self.assertNotIn("chat_turn", source)
        self.assertNotIn("ENABLE_PREOUTPUT_CHECK", source)
        self.assertNotIn("local_retrieve", source)
        self.assertNotIn("SYSTEM_PROMPT", source)
        self.assertIn("MINIMAL_TUTOR_PROMPT", source)
        self.assertNotIn("sk-", source)

    def test_report_marks_live_and_single_variable(self):
        mod = load_module()
        sample = [{"case": mod.CASES[0], "a": "A output", "b": "B output"}]
        text = mod.build_report(sample)
        self.assertIn("DeepSeek live", text)
        self.assertIn("不跑完整 Agent", text)
        self.assertIn("唯一变量", text)
        self.assertIn("A：最小导师 Prompt", text)
        self.assertIn("B：最小导师 Prompt + E2", text)


if __name__ == "__main__":
    unittest.main()
