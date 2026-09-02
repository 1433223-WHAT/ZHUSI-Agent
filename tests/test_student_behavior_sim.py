"""真实学生行为模拟回归测试。

来源：2026-08-17 用户实测 + 学生行为模拟——真实学生不会按 AI 引导走，
会挤牙膏、答非所问、反悔、含糊评价、反问、带情绪。这些行为暴露了
pending_clarification 跨轮污染、撤销正则误判、clarify 误判三个缺陷。

本测试锁定：系统在"混乱真实对话"中的状态处理与边界行为。
"""
import unittest
from unittest.mock import patch

from conversation_state import empty_state, update_state
from intent_router import route as router_route


class RetractionBehaviorTests(unittest.TestCase):
    """S4 反悔：'算了/不算'应走撤销，不误伤求助与状态表达。"""

    def test_retraction_words_trigger_retract(self):
        for msg in [
            "算了算了，我刚才说的不算，别搞那么复杂。",
            "撤销刚才的决定。",
            "我说的不作数。",
        ]:
            state = update_state(empty_state(), "场地北侧是村里的路", 1)
            state["project"]["site"] = {"value": "北侧是村里的路", "status": "confirmed", "source": "student", "turn_id": 1}
            updated = update_state(state, msg, 2)
            self.assertIn("撤销", updated.get("pending_clarification", ""),
                          f"'{msg}' 应进入撤销分支")

    def test_help_and_pressure_do_not_trigger_retract(self):
        for msg in [
            "你说我到底该怎么做啊？下周就要交概念了。",
            "我还没想好，急死了，感觉要来不及了。",
        ]:
            state = empty_state()
            updated = update_state(state, msg, 1)
            self.assertEqual("", updated.get("pending_clarification", ""),
                             f"'{msg}' 不应触发撤销/修改澄清")


class PendingClarificationLifetimeTests(unittest.TestCase):
    """S4→S5：遗留 pending 不应污染后续轮次。"""

    def test_pending_is_single_turn(self):
        from architect_chat import chat_turn
        from conversation_state import record_ai_question
        # 构造 S4 触发 pending 的状态
        state = empty_state()
        state = record_ai_question(state, "你想撤销哪一项决定？", "site", 1)
        state["project"]["site"] = {"value": "北侧是村里的路", "status": "confirmed", "source": "student", "turn_id": 1}
        # S5：学生说新话题（木屋顶），不应被 pending 劫持
        with patch("architect_chat.router_classify", return_value=None):
            with patch("architect_chat._call_deepseek", return_value="木屋顶是否保留需要结构评估。") as mock_model:
                result = chat_turn("对了，屋顶是木头的，你觉得能保留吗？", [], state, turn_id=2)
                self.assertNotIn("你想撤销", result["reply"])
                self.assertNotIn("你想修改", result["reply"])
                self.assertIn("屋顶", result["reply"])


class ClarifyScopeTests(unittest.TestCase):
    """S5/S8：含具体信息的问题与反问不应走 clarify。"""

    def test_concrete_info_question_not_clarify(self):
        cls = {
            "intent": "design_review", "design_stage": "development",
            "info_status": "insufficient", "decision_status": "exploring",
            "needs": ["none"], "reason": "含具体信息",
        }
        result = router_route("房子很旧，屋顶是木头的。你觉得能保留吗？", None, cls)
        self.assertNotEqual("clarify", result["pre_action"])

    def test_counter_question_not_clarify(self):
        cls = {
            "intent": "design_review", "design_stage": "development",
            "info_status": "insufficient", "decision_status": "exploring",
            "needs": ["none"], "reason": "反问",
        }
        result = router_route("那你觉得呢？换你你会怎么做？", None, cls)
        self.assertNotEqual("clarify", result["pre_action"])

    def test_true_vague_review_still_clarify(self):
        cls = {
            "intent": "design_review", "design_stage": "development",
            "info_status": "insufficient", "decision_status": "exploring",
            "needs": ["clarify"], "reason": "模糊评价",
        }
        result = router_route("感觉有点怪，不太对劲。", None, cls)
        self.assertEqual("clarify", result["pre_action"])


class AnswerIgnoredBehaviorTests(unittest.TestCase):
    """S2 答非所问：学生不回答 AI 问题时，不得把 AI 问题当学生事实。"""

    def test_unanswered_question_stays_pending(self):
        from architect_chat import _model_state
        from conversation_state import record_ai_question
        state = empty_state()
        state = record_ai_question(state, "你希望主要使用者是谁？", "goals", 1)
        model_state = _model_state(state)
        self.assertEqual(1, len(model_state.get("pending_questions", [])))
        self.assertEqual([], model_state["student_decisions"])


if __name__ == "__main__":
    unittest.main()
