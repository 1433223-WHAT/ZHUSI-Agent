from pathlib import Path
import importlib.util
import unittest


BASE = Path(__file__).resolve().parents[1]
SCRIPT = BASE / "_e3_art_reasoning_trace_experiment.py"


def load_module():
    spec = importlib.util.spec_from_file_location("e3_art", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class E3ArtReasoningTraceExperimentTests(unittest.TestCase):
    def test_script_is_minimal_art_ab_not_full_agent(self):
        mod = load_module()
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertEqual(3, len(mod.CASES))
        self.assertIn("Architectural Reasoning Trace", mod.ART_PROMPT)
        self.assertIn("不要向用户展示", mod.ART_PROMPT)
        self.assertIn("道路直接等于入口", mod.ART_PROMPT)
        self.assertNotIn("_call_deepseek", source)
        self.assertNotIn("chat_turn", source)
        self.assertNotIn("ENABLE_PREOUTPUT_CHECK", source)
        self.assertNotIn("local_retrieve", source)
        self.assertNotIn("SYSTEM_PROMPT", source)
        self.assertNotIn("sk-", source)

    def test_report_has_requested_sections(self):
        mod = load_module()
        sample = []
        for case in mod.CASES:
            sample.append({
                "case": case,
                "a": "A output",
                "b": "B output 如果 需要验证",
                "judge": {
                    "a_bad": 1,
                    "b_bad": 0,
                    "a_good": 0,
                    "b_good": 1,
                    "a_verify": 0,
                    "b_verify": 2,
                    "improved": True,
                },
            })
        text = mod.build_report(sample)
        self.assertIn("# E3 ART 实验", text)
        self.assertIn("### A组输出", text)
        self.assertIn("### B组输出", text)
        self.assertIn("免责声明数量", text)
        self.assertIn("道路→入口：改善", text)
        self.assertIn("最终：", text)


if __name__ == "__main__":
    unittest.main()
