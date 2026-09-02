"""真实用户行为回归测试：用户不按 AI 引导走时的边界保护。

来源：2026-08-17 用户实测暴露——用户没回答 AI 的问题（"使用者是谁"），
直接问新问题（"该有哪些区域"），AI 把 AI 自己问的选项当成学生已确认事实
（"你刚才说'村里的孩子放学后来'……"）。

本测试锁定：AI 不得把悬空问题/自己问的选项当作学生事实。
"""
import unittest
from unittest.mock import patch

from architect_chat import _model_state
from conversation_state import empty_state, record_ai_question


class PendingQuestionStateTests(unittest.TestCase):
    def test_unanswered_question_is_marked_pending(self):
        state = empty_state()
        state = record_ai_question(state, "你希望主要使用者是谁？是孩子放学后来，还是村民日常来？", "goals", 1)
        model_state = _model_state(state)
        pending = model_state.get("pending_questions", [])
        self.assertEqual(1, len(pending))
        self.assertEqual("goals", pending[0]["dimension"])
        self.assertIn("使用者", pending[0]["question"])

    def test_answered_question_is_not_pending(self):
        from conversation_state import answer_pending_question
        state = empty_state()
        state = record_ai_question(state, "你希望主要使用者是谁？", "goals", 1)
        state = answer_pending_question(state, "主要是村民日常来", 2)
        model_state = _model_state(state)
        self.assertEqual(0, len(model_state.get("pending_questions", [])))

    def test_unanswered_rule_is_injected_into_context(self):
        # 验证 _call_deepseek 的 context 含 unanswered_rule 且 pending_questions 被注入
        from architect_chat import _call_deepseek
        state = empty_state()
        state = record_ai_question(state, "你希望主要使用者是谁？是孩子放学后来，还是村民日常来？", "goals", 1)
        with patch("architect_chat.requests.post") as mock_post:
            import unittest.mock as mock
            response = mock.Mock()
            response.raise_for_status.return_value = None
            response.json.return_value = {"choices": [{"message": {"content": "正常回复"}}]}
            mock_post.return_value = response
            _call_deepseek(
                [{"role": "user", "content": "我这个图书室该有哪些区域"}],
                state, [], "general_architecture_chat", [],
                "测试策略",
            )
        context_json = mock_post.call_args.kwargs["json"]["messages"][-2]["content"]
        self.assertIn("unanswered_rule", context_json)
        self.assertIn("pending_questions", context_json)
        self.assertIn("不得把", context_json)

    def test_pending_question_content_is_not_student_fact(self):
        # 核心断言：模型状态里，未回答的问题内容必须与"已确认事实"分离
        state = empty_state()
        state["project"]["site"] = {
            "value": "北侧主路，南侧樟树", "status": "confirmed", "source": "student", "turn_id": 1,
        }
        state = record_ai_question(state, "是孩子放学后来，还是村民日常来？", "goals", 2)
        model_state = _model_state(state)
        # 已确认事实在 project，悬空问题在 pending_questions，两者分离
        self.assertIn("北侧主路", str(model_state["project"]["site"]))
        self.assertIn("放学后来", str(model_state["pending_questions"]))
        # pending_questions 绝不能出现在 student_decisions 或 student_intent
        self.assertEqual([], model_state["student_decisions"])
        self.assertEqual([], model_state["student_intent"])


if __name__ == "__main__":
    unittest.main()
