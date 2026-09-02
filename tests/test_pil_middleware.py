import unittest
from unittest.mock import patch
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import architect_chat as ac


class PilMiddlewareTests(unittest.TestCase):
    def test_pil_middleware_is_noop_when_disabled(self):
        old_enabled = ac.ENABLE_PIL_MIDDLEWARE
        try:
            ac.ENABLE_PIL_MIDDLEWARE = False
            result = ac._apply_pil_middleware_if_enabled(
                draft="东侧道路应该作为主入口。",
                state={},
                policy="policy",
            )
            self.assertEqual(result["reply"], "东侧道路应该作为主入口。")
            self.assertIs(result["applied"], False)
        finally:
            ac.ENABLE_PIL_MIDDLEWARE = old_enabled

    def test_pil_middleware_calls_boundary_and_final_when_enabled(self):
        old_enabled = ac.ENABLE_PIL_MIDDLEWARE
        calls = []

        def fake_boundary(draft, state, policy):
            calls.append(("boundary", draft, policy))
            return "把东侧主入口降级为入口候选。"

        def fake_final(draft, boundary_result, state, policy):
            calls.append(("final", draft, boundary_result))
            return "如果东侧承担主要到达，可以考虑作为入口候选。"

        try:
            ac.ENABLE_PIL_MIDDLEWARE = True
            with patch.object(ac, "_pil_boundary_check", fake_boundary), patch.object(ac, "_pil_final_generate", fake_final):
                result = ac._apply_pil_middleware_if_enabled(
                    draft="东侧道路应该作为主入口。",
                    state={},
                    policy="policy",
                )
            self.assertEqual(result["reply"], "如果东侧承担主要到达，可以考虑作为入口候选。")
            self.assertIs(result["applied"], True)
            self.assertEqual(result["boundary_check"], "把东侧主入口降级为入口候选。")
            self.assertEqual(calls, [
                ("boundary", "东侧道路应该作为主入口。", "policy"),
                ("final", "东侧道路应该作为主入口。", "把东侧主入口降级为入口候选。"),
            ])
        finally:
            ac.ENABLE_PIL_MIDDLEWARE = old_enabled

    def test_final_generator_prompt_makes_boundary_check_mandatory(self):
        self.assertIn("PIL Boundary Check 高于内部草稿", ac.PIL_FINAL_GENERATOR_PROMPT)
        self.assertIn("不允许保留原强断言", ac.PIL_FINAL_GENERATOR_PROMPT)
        self.assertIn("必须执行 Boundary Check", ac.PIL_FINAL_GENERATOR_PROMPT)


if __name__ == "__main__":
    unittest.main()
