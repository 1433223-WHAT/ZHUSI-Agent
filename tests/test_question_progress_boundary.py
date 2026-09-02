import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import architect_chat as ac
from conversation_state import empty_state


class QuestionProgressBoundaryTests(unittest.TestCase):
    def test_user_unavailable_answer_marks_existing_question(self):
        state = empty_state()
        state["question_history"] = [{
            "question": "老师更看重回应场地还是建筑本体？",
            "dimension": "goals",
            "answer": "",
            "turn_id": 1,
        }]

        ac._mark_recent_question_unavailable(
            state,
            "老师没说更看重哪个，我也没有这项要求。",
        )

        self.assertEqual("unavailable", state["question_history"][-1]["status"])

    def test_unavailable_question_is_removed_when_model_repeats_it(self):
        state = empty_state()
        state["question_history"] = [{
            "question": "老师更看重回应场地还是建筑本体？",
            "dimension": "goals",
            "answer": "",
            "status": "unavailable",
            "turn_id": 1,
        }]
        reply = (
            "先给出不依赖老师偏好的功能关系草图。\n\n"
            "老师对这次作业更侧重具体场地，还是更侧重建筑本体？"
        )

        result = ac._apply_redundant_question_boundary(
            reply,
            state,
            "老师真的没说，你别再问这个了。",
        )

        self.assertNotIn("老师对这次作业", result)
        self.assertIn("功能关系草图", result)

    def test_recent_local_streak_requires_overall_reconnection(self):
        state = empty_state()
        state["interaction_log"] = [
            {"ai_reply": "继续深化工坊玻璃界面和观察窗的位置。"},
            {"ai_reply": "再比较舞蹈教室走道一侧的窗高和玻璃范围。"},
        ]

        policy = ac._conversation_progress_policy(
            state,
            "这个局部可以继续试，但现在还没有决定。",
        )

        self.assertIn("回接整体", policy)
        self.assertIn("不得继续追加局部二选一", policy)
        self.assertIn("功能关系", policy)

    def test_local_streak_reconnects_to_latest_existing_overall_anchor(self):
        state = empty_state()
        state["interaction_log"] = [
            {"ai_reply": "整体先比较单入口与双层级入口两种空间骨架。"},
            {"ai_reply": "继续深化入口灰空间、门厅和玻璃界面。"},
            {"ai_reply": "再看走道、观察窗和玻璃隔断怎么连接。"},
        ]

        policy = ac._conversation_progress_policy(
            state,
            "嗯，可以继续看看，我还是没有拍板。",
        )

        self.assertIn("原有整体讨论锚点", policy)
        self.assertIn("单入口与双层级入口", policy)
        self.assertIn("不得另立新的整体组织原则", policy)

    def test_overall_history_does_not_trigger_local_reconnection(self):
        state = empty_state()
        state["interaction_log"] = [
            {"ai_reply": "先建立整体功能关系和主流线骨架。"},
            {"ai_reply": "再比较总体布局、体量和场地关系。"},
        ]

        self.assertEqual("", ac._conversation_progress_policy(state, "继续看看。"))

    def test_negated_overall_mention_is_still_local_only(self):
        reply = (
            "继续深化工坊玻璃界面、走道和观察窗。"
            "这只是局部处理，不牵动整体布局，也不影响整栋建筑。"
        )

        self.assertTrue(ac._reply_is_local_design(reply))

    def test_comparison_does_not_pressure_student_to_choose_main_route(self):
        old_enabled = ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY
        try:
            ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = True
            draft = (
                "方向 A 和方向 B 都给出成立条件、收益与代价。"
                "我建议你先只选一个作为主策略，另一个作为辅助。"
                "两张草图都可以继续检验。"
            )

            result = ac._apply_candidate_commitment_body_boundary(
                draft,
                "请先给我两个能比较的局部方向。",
                "compare_cases",
                {},
            )

            self.assertNotIn("只选一个作为主策略", result)
            self.assertIn("相同评价标准", result)
            self.assertIn("两张草图", result)
        finally:
            ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = old_enabled


if __name__ == "__main__":
    unittest.main()
