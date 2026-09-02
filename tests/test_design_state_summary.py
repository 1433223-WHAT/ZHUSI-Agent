import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import architect_chat as ac


class DesignStateSummaryTests(unittest.TestCase):
    def test_design_state_summary_is_noop_when_disabled(self):
        old_enabled = ac.ENABLE_DESIGN_STATE_SUMMARY
        try:
            ac.ENABLE_DESIGN_STATE_SUMMARY = False
            policy = ac._apply_design_state_hidden_summary(
                "base policy",
                {"current_stage": "探索"},
                "我还没决定入口，先看看。",
                "design_request",
            )
            self.assertEqual(policy, "base policy")
        finally:
            ac.ENABLE_DESIGN_STATE_SUMMARY = old_enabled

    def test_design_state_summary_contains_fixed_fields_when_enabled(self):
        old_enabled = ac.ENABLE_DESIGN_STATE_SUMMARY
        state = {
            "current_stage": "方案探索",
            "project": {"site": "东侧社区道路，南侧公园"},
            "student_decisions": [],
            "assumptions": [{"content": "东侧入口候选", "status": "candidate"}],
            "unresolved_questions": [{"question": "主要到达人流未确认"}],
        }
        original = dict(state)
        try:
            ac.ENABLE_DESIGN_STATE_SUMMARY = True
            policy = ac._apply_design_state_hidden_summary(
                "base policy",
                state,
                "我只是想先看看东侧入口能不能成立，还没决定。",
                "design_request",
            )
            self.assertIn("当前设计阶段", policy)
            self.assertIn("已确认条件", policy)
            self.assertIn("当前候选状态", policy)
            self.assertIn("未确认决策", policy)
            self.assertIn("不得把候选方向写成既定方案", policy)
            self.assertEqual(state, original)
        finally:
            ac.ENABLE_DESIGN_STATE_SUMMARY = old_enabled

    def test_design_state_summary_reads_existing_issue_text_field(self):
        state = {
            "issue_register": {
                "issue-2-1": {
                    "text": "中央中庭作为可撤回候选",
                    "origin": "ai",
                    "status": "candidate",
                }
            }
        }

        summary = ac._design_state_hidden_summary(
            state,
            "这个方向还行，你接着往下做。",
            "design_request",
        )

        self.assertIn("中央中庭作为可撤回候选", summary)

    def test_design_state_summary_uses_collaboration_focus_stage(self):
        state = {
            "current_stage": "探索",
            "collaboration_focus": {
                "design_stage": {
                    "value": "review_revision",
                    "status": "confirmed",
                }
            },
        }

        summary = ac._design_state_hidden_summary(
            state,
            "这是我的第一版方案，继续帮我调整。",
            "design_request",
        )

        self.assertIn("当前设计阶段：review_revision", summary)

    def test_design_state_summary_uses_clean_project_values_and_confirmed_decisions(self):
        state = {
            "project": {
                "site": {
                    "value": "北侧临城市道路",
                    "status": "confirmed",
                    "source": "student",
                    "turn_id": 1,
                }
            },
            "student_decisions": [
                {
                    "value": "采用中央中庭组织",
                    "source": "student",
                    "turn_id": 3,
                }
            ],
        }

        summary = ac._design_state_hidden_summary(
            state,
            "继续深化入口和流线。",
            "design_request",
        )

        self.assertIn("site: 北侧临城市道路", summary)
        self.assertIn("采用中央中庭组织", summary)
        self.assertNotIn("'turn_id': 1", summary)


if __name__ == "__main__":
    unittest.main()
